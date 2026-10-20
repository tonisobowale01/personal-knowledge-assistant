"""Focused live regressions for history-aware single-search retrieval."""
import json,sys
from pathlib import Path
from types import SimpleNamespace
from time import perf_counter
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import rag

cases=[
    {'id':'sjf_all','question':'What are its advantages','course':None,'history':[('user','What is SJF'),('assistant','SJF stands for Shortest Job First. It is a non-preemptive CPU scheduling algorithm that selects the process with the shortest burst time (estimated CPU time) to execute next.')]},
    {'id':'sjf_os','question':'What are its advantages','course':'Operating Systems','history':[('user','What is SJF'),('assistant','SJF selects the shortest estimated CPU burst next.')]},
    {'id':'round_robin_quantum','question':'What happens if its time quantum is too large?','course':'Operating Systems','history':[('user','Explain Round Robin scheduling.'),('assistant','Round Robin gives each process a fixed time quantum.')]},
    {'id':'star_failure','question':'What happens if that central device fails?','course':'Networking','history':[('user','Explain star topology.'),('assistant','Devices connect to a central hub or switch.')]},
    {'id':'topic_switch','question':'What are its advantages?','course':'Operating Systems','history':[('user','What is SJF?'),('assistant','SJF selects short jobs.'),('user','Explain Round Robin scheduling.'),('assistant','Round Robin uses a time quantum.')]},
]
original=rag.retrieve
trace=[]
def record(*args,**kwargs):
    result=original(*args,**kwargs);trace.append(result);return result
rag.retrieve=record
report={'cases':[],'limitations':'Focused development cases, manual review required. No extra model rewriting; unchanged model and answer prompt. Timings are single runs with cache effects.'}
for case in cases:
    trace.clear();history=[SimpleNamespace(role=r,content=t) for r,t in case['history']]
    raw=original(case['question'],case['course'],rag.collection,lambda q:rag.ollama.embed(model='nomic-embed-text',input=q)['embeddings'][0])
    start=perf_counter();final=None
    for event in rag.stream_question(case['question'],course=case['course'],history=history):
        if event['type']=='done':final=event
    row={'case':case,'answer':final['answer'],'timings':final.get('timings',{}),'wall_seconds':perf_counter()-start,'raw_query_passages':raw['passages'],'actual_retrieval':trace[-1]}
    report['cases'].append(row)
    (ROOT/'followup_check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(case['id'],row['answer'],flush=True)
