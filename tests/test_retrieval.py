"""Checks for the restored baseline, including parity with the original source."""
import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.retrieval import retrieve, retrieval_query
ROOT = Path(__file__).resolve().parents[1]


def result(texts, distances):
    return dict(documents=[texts], distances=[distances],
                metadatas=[[{'file_name':'notes.txt','page_label':str(i)} for i in range(len(texts))]],
                ids=[[str(i) for i in range(len(texts))]])


class Retrieval(unittest.TestCase):
    def test_single_raw_query_and_all_courses_has_no_filter(self):
        collection = Mock(); collection.query.return_value = result(['Evidence'], [.3])
        embed = Mock(return_value=[1])
        retrieve('What is SJF?', None, collection, embed)
        embed.assert_called_once_with('What is SJF?')
        collection.query.assert_called_once_with(query_embeddings=[[1]], n_results=20,
            include=['documents','metadatas','distances'])

    def test_selected_course_adds_only_metadata_filter(self):
        collection = Mock(); collection.query.return_value = result(['Evidence'], [.3])
        retrieve('What is SJF?', 'Networking', collection, lambda q:[1])
        self.assertEqual(collection.query.call_args.kwargs['where'], {'course':'Networking'})

    def test_original_best_match_cutoff_keeps_full_neighbours(self):
        collection = Mock(); collection.query.return_value = result(['Full table','Full narrative'], [1.05,1.8])
        evidence = retrieve('Question', None, collection, lambda q:[1])
        self.assertEqual([p['text'] for p in evidence['passages']], ['Full table','Full narrative'])
        self.assertEqual(evidence['distance_limit'], 1.1)

    def test_empty_weak_and_boundary_results(self):
        collection = Mock()
        for data, count in [(result([],[]),0), (result(['Weak'],[1.1001]),0), (result(['Boundary'],[1.1]),1)]:
            collection.query.return_value = data
            self.assertEqual(len(retrieve('Question', None, collection, lambda q:[1])['passages']), count)

    def load_modules(self, collection, model):
        chroma = SimpleNamespace(PersistentClient=Mock(return_value=SimpleNamespace(get_or_create_collection=Mock(return_value=collection))))
        embedder = SimpleNamespace(embed=Mock(return_value={'embeddings':[[1]]}))
        modules = {}
        with patch.dict(sys.modules, {'chromadb':chroma, 'ollama':embedder,
                'llama_index.llms.ollama':SimpleNamespace(Ollama=Mock(return_value=model))}):
            for name, path in [('baseline',ROOT/'app/rag.py'), ('original',ROOT/'benchmarks/original_rag.py')]:
                spec=importlib.util.spec_from_file_location(name,path)
                module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
                modules[name]=module
        return modules, embedder

    def test_standalone_prompt_sources_and_query_match_original(self):
        collection=Mock(); collection.query.return_value=result(['Complete first chunk','Complete second chunk'],[1.05,1.8])
        model=Mock(); model.complete.return_value=SimpleNamespace(text='Original answer')
        modules, embedder=self.load_modules(collection,model)
        for course in [None,'Networking']:
            original=modules['original'].ask_question('What is SJF?',course)
            original_query=collection.query.call_args.kwargs
            original_prompt=model.complete.call_args.args[0]
            prompt,sources,_,passages,resolved=modules['baseline'].prepare_evidence('What is SJF?',course)
            self.assertEqual(prompt,original_prompt)
            self.assertEqual(sources,original['sources'])
            current_query=collection.query.call_args.kwargs
            self.assertEqual(current_query['n_results'],20)
            self.assertEqual({k:v for k,v in current_query.items() if k!='n_results'},
                             {k:v for k,v in original_query.items() if k!='n_results'})
            self.assertEqual(resolved,'What is SJF?')
            self.assertEqual(len(passages),2)

    def test_multipart_question_is_one_stream_and_one_search(self):
        collection=Mock(); collection.query.return_value=result(['All evidence'],[.2])
        model=Mock(); model.stream_complete.return_value=iter([
            SimpleNamespace(delta='Plain answer',raw={}),
            SimpleNamespace(delta='',raw={'done':True,'done_reason':'stop','eval_count':2,'eval_duration':1000000000})])
        modules, embedder=self.load_modules(collection,model)
        events=list(modules['baseline'].stream_question('What are alpha, beta, and gamma?'))
        collection.query.assert_called_once()
        model.stream_complete.assert_called_once()
        model.complete.assert_not_called()
        self.assertEqual(sum(e['type']=='done' for e in events),1)
        self.assertEqual(events[-1]['answer'],'Plain answer')
        self.assertIn('prompt_eval_seconds',events[-1]['timings'])
        self.assertIn('retrieval_seconds',events[-1]['timings'])

    def test_followup_search_uses_user_topic_without_a_model_rewrite(self):
        collection=Mock(); collection.query.return_value=result(['Evidence'],[.2])
        model=Mock(); modules, embedder=self.load_modules(collection,model)
        history=[SimpleNamespace(role='user',content='Round Robin')]
        prompt,_,_=modules['baseline'].prepare_question('What are its drawbacks?',history=history)
        self.assertIn('Round Robin',prompt)
        embedder.embed.assert_called_once_with(model='nomic-embed-text',input='Round Robin\nFollow-up: What are its drawbacks?')
        model.complete.assert_not_called()

    def test_followup_chain_keeps_latest_explicit_topic(self):
        history=[SimpleNamespace(role='user',content='Explain Alpha.'),SimpleNamespace(role='assistant',content='WRONG_ASSISTANT_FACT'),SimpleNamespace(role='user',content='Explain Beta.'),SimpleNamespace(role='assistant',content='ANOTHER_WRONG_FACT'),SimpleNamespace(role='user',content='What are its benefits?')]
        query=retrieval_query('And its drawbacks?',history)
        self.assertEqual(query,'Explain Beta.\nFollow-up: And its drawbacks?')
        self.assertNotIn('WRONG',query)
        self.assertEqual(retrieval_query('Explain Gamma.',history),'Explain Gamma.')
        self.assertEqual(retrieval_query('What are its benefits?',[]),'What are its benefits?')

    def test_answer_keeps_topic_after_it_leaves_recent_history(self):
        collection=Mock(); collection.query.return_value=result(['Evidence'],[.2])
        model=Mock(); modules, embedder=self.load_modules(collection,model)
        history=[SimpleNamespace(role='user',content='Explain Round Robin scheduling.'),
                 SimpleNamespace(role='assistant',content='It uses a fixed time quantum.'),
                 SimpleNamespace(role='user',content='What are its advantages?'),
                 SimpleNamespace(role='assistant',content='It is fair.'),
                 SimpleNamespace(role='user',content='What are its disadvantages?'),
                 SimpleNamespace(role='assistant',content='Small quanta increase switching overhead.')]
        prompt,_,_,_,resolved=modules['baseline'].prepare_evidence('What happens if it is too large?',history=history)
        self.assertEqual(resolved,'What happens if it is too large?')
        question_section=prompt.split('Question:')[1].split('Conversation')[0]
        self.assertIn(resolved,question_section)
        self.assertNotIn('Round Robin',question_section)
        self.assertIn('user: Explain Round Robin scheduling.',prompt.split('Conversation')[1])
        embedder.embed.assert_called_once_with(model='nomic-embed-text',input='Explain Round Robin scheduling.\nFollow-up: '+resolved)
        model.complete.assert_not_called()

    def test_refusal_has_no_generation(self):
        collection=Mock(); collection.query.return_value=result([],[])
        model=Mock(); modules,_=self.load_modules(collection,model)
        answer=modules['baseline'].ask_question('Missing')
        self.assertEqual(answer,{'answer':'I could not find that in the notes.','sources':[]})
        model.stream_complete.assert_not_called()

    def test_person_references_keep_explicit_user_topic(self):
        history=[SimpleNamespace(role='user',content='Who is Wagner?'),
                 SimpleNamespace(role='assistant',content='Richard Wagner.'),
                 SimpleNamespace(role='user',content='Who was he?'),
                 SimpleNamespace(role='assistant',content='Richard Wagner.')]
        for question in ['What did he believe in?','What is unique about him?','What were his ideas?']:
            self.assertEqual(retrieval_query(question,history),'Who is Wagner?\nFollow-up: '+question)
        self.assertEqual(retrieval_query('Who is Puccini?',history),'Who is Puccini?')
        self.assertEqual(retrieval_query('Who is her father?',[SimpleNamespace(role='user',content='Who leads the Valkyries?')]),
                         'Who leads the Valkyries?\nFollow-up: Who is her father?')

    def test_heading_match_recovers_relevant_lower_ranked_evidence_without_more_prompt_passages(self):
        collection=Mock()
        texts=['General background\nBackground details']*8+['Resource waiting conditions\nAll necessary conditions and their meaning']
        collection.query.return_value=result(texts,[.2+i*.02 for i in range(len(texts))])
        evidence=retrieve('What conditions apply to resources?',None,collection,lambda q:[1])
        self.assertEqual(len(evidence['candidates']),9)
        self.assertEqual(len(evidence['passages']),5)
        self.assertEqual(evidence['passages'][0]['id'],'8')
        self.assertEqual(evidence['passages'][0]['text'],texts[-1])

    def test_heading_match_cannot_bypass_weak_semantic_gate(self):
        collection=Mock();collection.query.return_value=result(['Exact requested topic'],[1.2])
        self.assertEqual(retrieve('Exact requested topic',None,collection,lambda q:[1])['passages'],[])


if __name__ == '__main__':
    unittest.main()
