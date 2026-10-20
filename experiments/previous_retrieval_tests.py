import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.retrieval import retrieve, search_queries, compact_passages, focus_passage, restore_table_context

def result(texts,distances):
 return {'documents':[texts],'distances':[distances], 'metadatas':[[{'file_name':'notes','page_label':str(i)} for i in range(len(texts))]],'ids':[[str(i) for i in range(len(texts))]]}

class Retrieval(unittest.TestCase):
 def test_no_history_skips_model_rewrite(self):
  complete=Mock()
  self.assertEqual(search_queries(' What is FCFS? ',[],complete),['What is FCFS?'])
  complete.assert_not_called()
 def test_preserves_identifiers_and_falls_back_on_failure(self):
  history=[SimpleNamespace(role='user',content='Scheduling')]
  self.assertEqual(search_queries('What about FCFS?',history,Mock(return_value=SimpleNamespace(text='What about scheduling?'))),['What about FCFS?'])
  with self.assertLogs('app.retrieval', level='WARNING'):
   self.assertEqual(search_queries('Explain it',history,Mock(side_effect=RuntimeError())),['Explain it'])
 def test_followup_searches_both_forms_and_filters_duplicates(self):
  c=Mock();c.query.side_effect=[result(['Good','Bad'],[.2,1.5]),result([' good ','Other'],[.3,.4])]
  embed=Mock(return_value=[1])
  output=retrieve('What about it?','OS',[SimpleNamespace(role='user',content='Topic')],c,embed,Mock(return_value=SimpleNamespace(text='What about Topic?')))
  self.assertEqual([p['text'] for p in output['passages']],['Good','Other'])
  self.assertEqual(embed.call_count,2)
  for call in c.query.call_args_list: self.assertEqual(call.kwargs['where'],{'course':'OS'})
 def test_empty_results_and_all_weak_results(self):
  for data in [result([],[]),result(['Weak'],[2]),result(['Invalid'],[float('nan')])]:
   c=Mock();c.query.return_value=data
   self.assertEqual(retrieve('Question',None,[],c,Mock(return_value=[1]),Mock())['passages'],[])
 def test_calibrated_cutoff_filters_each_passage(self):
  c=Mock();c.query.return_value=result(['Supported','Too far'],[.97,1.01])
  output=retrieve('Question',None,[],c,lambda q:[1],Mock())
  self.assertEqual([p['text'] for p in output['passages']],['Supported'])
  self.assertEqual(output['distance_limit'],1.0)

 def test_legacy_keeps_weak_neighbors_for_comparison(self):
  c=Mock();c.query.return_value=result(['Good','Weak'],[.1,2])
  model=Mock(return_value=SimpleNamespace(text='Question'))
  self.assertEqual(len(retrieve('Question',None,[],c,lambda q:[1],model,legacy=True)['passages']),2)
  self.assertEqual(len(retrieve('Question',None,[],c,lambda q:[1],model)['passages']),1)

 def test_answer_prompt_contains_only_filtered_passages(self):
  import importlib.util
  from unittest.mock import patch
  collection=Mock()
  collection.query.return_value=result(['Supported evidence','Weak unrelated evidence'],[.2,1.8])
  chroma=SimpleNamespace(PersistentClient=Mock(return_value=SimpleNamespace(get_or_create_collection=Mock(return_value=collection))))
  model=Mock();model.stream_complete.return_value=iter([SimpleNamespace(delta='Answer',raw={}),SimpleNamespace(delta='',raw={'done':True,'done_reason':'stop'})])
  ollama=SimpleNamespace(embed=Mock(return_value={'embeddings':[[1]]}))
  with patch.dict(sys.modules,{'chromadb':chroma,'ollama':ollama,'llama_index.llms.ollama':SimpleNamespace(Ollama=Mock(return_value=model))}):
   spec=importlib.util.spec_from_file_location('tested_rag',Path(__file__).resolve().parents[1]/'app/rag.py')
   rag=importlib.util.module_from_spec(spec);spec.loader.exec_module(rag)
   answer=rag.ask_question('Question')
   self.assertEqual(answer['sources'],[{'file':'notes','page':'0'}])
   model.stream_complete.assert_called_once()
   prompt=model.stream_complete.call_args.args[0]
   self.assertIn('Supported evidence',prompt)
   self.assertNotIn('Weak unrelated evidence',prompt)
   collection.query.return_value=result([],[])
   model.stream_complete.reset_mock()
   self.assertEqual(rag.ask_question('Missing')['sources'],[])
   model.stream_complete.assert_not_called()
   collection.query.return_value=result(['Round Robin has context-switch overhead.'],[.2])
   model.complete.return_value=SimpleNamespace(text='What are the drawbacks of Round Robin?')
   history=[SimpleNamespace(role='assistant',content='OLD_ANSWER_SENTINEL '+('long answer '*100))]
   prompt,_,_=rag.prepare_question('What are its drawbacks?',history=history)
   self.assertNotIn('OLD_ANSWER_SENTINEL',prompt)
   self.assertIn('What are the drawbacks of Round Robin?',prompt)
   model.complete.side_effect=RuntimeError('Rewrite failed')
   with self.assertLogs('app.retrieval',level='WARNING'):
    prompt,_,_=rag.prepare_question('What are its drawbacks?',history=history)
   self.assertIn('OLD_ANSWER_SENTINEL',prompt)
   model.complete.side_effect=None
   collection.query.return_value=result(['Alpha isolates environments.','Beta provides high availability.','Gamma uses multiple cores.'],[.1,.2,.3])
   explanation='Alpha isolates environments. Beta provides high availability. Gamma uses multiple cores.'
   model.stream_complete.side_effect=lambda *args: iter([SimpleNamespace(delta='A supported explanation.',raw={}),SimpleNamespace(delta='',raw={'done':True,'done_reason':'stop'})])
   self.assertEqual(rag.definition_topics('What are alpha, beta, and gamma?'),['alpha','beta','gamma'])
   self.assertEqual(rag.definition_topics('What are it and that?'),[])
   self.assertEqual(rag.definition_topics('Compare alpha and beta'),[])
   events=list(rag.stream_question('What are alpha, beta, and gamma?'))
   self.assertEqual(sum(e['type']=='done' for e in events),1)
   self.assertTrue(all(topic+':' in events[-1]['answer'] for topic in ['alpha','beta','gamma']))
   self.assertEqual(events[-1]['timings']['parts'],3)
   for call in model.stream_complete.call_args_list:
    if 'EVERY requested topic' in call.args[0]:
     self.assertNotIn('Return up to 8 JSON',call.args[0])





 def test_compaction_keeps_comparison_evidence(self):
  passages=[{'text':'Bus uses a shared cable.', 'distance':.1}, {'text':'Star uses a central hub.', 'distance':.2}, {'text':'Extra detail.', 'distance':.3}, {'text':'Unrelated detail.', 'distance':.4}]
  self.assertEqual(len(compact_passages('Compare bus and star',passages)),2)
  self.assertEqual(len(compact_passages('Explain bus',passages)),2)
  self.assertEqual(compact_passages('Compare bus and star',passages)[:2],passages[:2])
 def test_compaction_removes_contained_overlap_keeps_new_explanation(self):
  first={'text':'one two three four five six seven eight nine ten eleven twelve'}
  overlap={'text':'two three four five six seven eight nine ten eleven'}
  novel={'text':'Failure of the main cable brings down the bus network.'}
  self.assertEqual(compact_passages('Explain failures',[first,overlap,novel]),[first,novel])

 def test_topic_introduction_beats_incidental_mention(self):
  star={'text':'Star topology connects devices to a hub. Much later it mentions a bus.'}
  other={'text':'Other unrelated topics and some extra details.'}
  bus={'text':'All devices connect to one cable called the bus. Cable failure disables all devices.'}
  selected=compact_passages('Compare bus and star topologies',[star,other,bus])
  self.assertIn(star,selected)
  self.assertIn(bus,selected)
  self.assertEqual(compact_passages('Explain bus',[star,other,bus])[0],bus)

 def test_focus_separates_star_and_mesh_properties(self):
  passage={'text':'The Star Topology uses a central hub.\nHub failure disables the whole network.\n\nThe Mesh Topology uses many connections.\nExpensive and complex.\n\nIn the Tree Topology devices form a hierarchy.', 'metadata':{'page_label':'7'}}
  focused=focus_passage('Compare bus and star topologies',passage)
  self.assertIn('Hub failure disables the whole network.',focused['text'])
  self.assertNotIn('Expensive and complex',focused['text'])
  self.assertNotIn('Tree',focused['text'])
  self.assertEqual(focused['metadata'],passage['metadata'])

 def test_labeled_definitions_are_not_blended(self):
  p={'text':'o Alpha system: Uses many independent units with their own local storage.\no Beta system: Uses multiple units on the same physical package for efficient communication.'}
  focused=focus_passage('What is beta?',p)
  self.assertIn('Beta system:',focused['text'])
  self.assertNotIn('Alpha system:',focused['text'])
 def test_variant_explanation_keeps_its_explicit_scope(self):
  p={'text':'Base selects the shortest task.\n  An arriving task can interrupt another\n  (in the Gamma variant).\nLong tasks may wait indefinitely.'}
  self.assertNotIn('interrupt',focus_passage('Why is Base unfair?',p)['text'])
  self.assertIn('Long tasks may wait indefinitely.',focus_passage('Why is Base unfair?',p)['text'])
  self.assertIn('interrupt',focus_passage('Explain Gamma',p)['text'])
  self.assertIn('interrupt',focus_passage('Compare the variants of Base',p)['text'])
 def test_table_context_recovery_preserves_numbered_section_and_source(self):
  p={'id':'notes-chunk-2','text':'| Name | Result |\n| BETA | Yes |','metadata':{'file_name':'notes.txt','course':'Course'},'distance':.2}
  c=Mock();c.get.side_effect=[{'ids':['notes-chunk-1','notes-chunk-2']},{'ids':['notes-chunk-1','notes-chunk-2'],'documents':['1. ALPHA\n--------\nAlpha uses arrival order and never starves.\n2. BETA\n--------\nBeta chooses the shortest task first.\nDisadvantages: Long tasks may wait indefinitely.','| Name | Result |\n| BETA | Yes |'],'metadatas':[{'file_name':'notes.txt','page_label':'1'},p['metadata']]}]
  restored=restore_table_context([p],c,'Course')
  focused=compact_passages('Why can BETA be unfair?',restored)
  self.assertIn('Long tasks may wait indefinitely.',focused[0]['text'])
  self.assertNotIn('Alpha uses arrival order',focused[0]['text'])
  self.assertEqual(focused[0]['metadata']['page_label'],'1')

if __name__=='__main__': unittest.main()
