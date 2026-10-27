"""Inspect reported cases before/after the pronoun fix; three live answers only."""
import hashlib,importlib.util,json,sys
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import rag
from app.retrieval import retrieve
spec=importlib.util.spec_from_file_location('issues_before',ROOT/'benchmarks/retrieval_before_person_references.py')
before=importlib.util.module_from_spec(spec);spec.loader.exec_module(before)
cases=json.loads((ROOT/'tests/issue_cases.json').read_text(encoding='utf-8'))
output=ROOT/'.run/reported_issues.json'
output.parent.mkdir(exist_ok=True)
data=rag.collection.get(include=['documents','metadatas'])
report={'corpus_sha256':hashlib.sha256(json.dumps(sorted(zip(data['ids'],data['documents'],data['metadatas'])),sort_keys=True).encode()).hexdigest(),
        'limitations':'Development cases from user screenshots. Retrieval traces require manual evidence review; source/page matches do not establish correctness. No model/prompt/ranking changes. Embeddings reused for identical queries; timings not a speed benchmark.',
        'rows':[]}
embeddings={}
def embed(q):
    if q not in embeddings:embeddings[q]=rag.ollama.embed(model='nomic-embed-text',input=q)['embeddings'][0]
    return embeddings[q]
for case in cases:
    courses={m['course'] for m in data['metadatas'] if m.get('file_name')==case['file']}
    if len(courses)!=1:raise RuntimeError(f"Expected exactly one indexed course for {case['file']}")
    course=next(iter(courses));history=[SimpleNamespace(**m) for m in case['history']]
    row={'case':case,'course':course}
    for mode,fn in [('before',before.retrieve),('after',retrieve)]:
        row[mode]=fn(case['question'],course,rag.collection,embed,history=history)
    report['rows'].append(row)
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(case['id'],json.dumps({m:{'query':row[m]['queries'][0],'pages':[(p['metadata'].get('file_name'),p['metadata'].get('page_label')) for p in row[m]['passages']]} for m in ['before','after']}),flush=True)
for row in report['rows']:
    if row['case']['id'] not in ['wagner_he','wotan_father','deadlock_natural']:continue
    final=None
    for event in rag.stream_question(row['case']['question'],course=row['course'],history=[SimpleNamespace(**m) for m in row['case']['history']]):
        if event['type']=='done':final=event
    if final is None:raise RuntimeError('No completed answer')
    row['live_answer']=final
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('ANSWER',row['case']['id'],json.dumps(final['answer']),flush=True)
