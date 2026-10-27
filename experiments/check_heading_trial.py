"""Read-only evidence check and focused live answers for heading ranking."""
import json,sys
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'experiments'))
from heading_trial import HeadingCollection
from app import rag
import importlib.util
spec=importlib.util.spec_from_file_location('heading_baseline',ROOT/'benchmarks/retrieval_before_heading_trial.py')
original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
retrieve,retrieval_query=original.retrieve,original.retrieval_query
base=rag.collection
prior=json.loads((ROOT/'.run/remaining_evidence.json').read_text())
cases=[dict(id=r['id'],question=r['question'],course=r['course'],history=r['history']) for r in prior['rows']]
cases+=json.loads((ROOT/'tests/answer_cases.json').read_text())
cases+=json.loads((ROOT/'tests/issue_cases.json').read_text())
out=ROOT/'.run/heading_trial.json';report={'rows':[],'protocol':'Only trial candidate selection changes: semantic top 20, generic first-two-line term overlap, choose five. Same gate/model/prompt/history/index. No production changes; live answers only for three deadlock phrasings.'}
memo={}
def embed(q):
    if q not in memo:memo[q]=rag.ollama.embed(model='nomic-embed-text',input=q)['embeddings'][0]
    return memo[q]
seen=set()
for case in cases:
    history=[SimpleNamespace(**m) for m in case.get('history',[])]
    if 'course' in case:course=case['course']
    else:
        metas=base.get(where={'file_name':case['file']},include=['metadatas'])['metadatas']
        course=metas[0]['course']
    key=(case['question'],course,json.dumps(case.get('history',[]),sort_keys=True))
    if key in seen:continue
    seen.add(key)
    trial=HeadingCollection(base,retrieval_query(case['question'],history))
    row=dict(case=case,course=course,baseline=retrieve(case['question'],course,base,embed,history=history),trial=retrieve(case['question'],course,trial,embed,history=history))
    report['rows'].append(row)
    out.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(case['id'],json.dumps({m:[(p['metadata'].get('file_name'),p['metadata'].get('page_label')) for p in row[m]['passages']] for m in ['baseline','trial']}),flush=True)
for row in report['rows']:
    if row['case']['id'] not in ['deadlock_natural','deadlock_four','deadlock_keywords']:continue
    # Run only the saved-history versions at the start of this report.
    if row['case'] not in cases[:5]:continue
    case=row['case'];history=[SimpleNamespace(**m) for m in case.get('history',[])]
    rag.collection=HeadingCollection(base,retrieval_query(case['question'],history))
    for event in rag.stream_question(case['question'],course=row['course'],history=history):
        if event['type']=='done':row['trial_answer']=event
    out.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('ANSWER',case['id'],json.dumps(row['trial_answer']['answer']),flush=True)
