"""Paired repeats with a warm model and a neutral prompt before each measurement."""
import argparse,json,sys
from pathlib import Path
from time import perf_counter
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    p=argparse.ArgumentParser();p.add_argument('--ids',nargs='+',default=['q14']);p.add_argument('--repeats',type=int,default=3);p.add_argument('--output',type=Path,default=ROOT/'chunking_paired.json');a=p.parse_args()
    import chromadb
    from app import rag
    baseline_client=chromadb.PersistentClient(path=str(ROOT/'chroma_db'))
    baseline=baseline_client.get_collection('test_notes_baseline_20261014')
    trial=chromadb.PersistentClient(path=str(ROOT/'chunking_trial_db_v2')).get_collection('test_notes')
    cases=[c for c in json.loads((ROOT/'tests/answer_cases.json').read_text(encoding='utf-8')) if c['id'] in a.ids]
    report={'protocol':'Unchanged application model/settings. Warm model with neutral Reply with OK prompt before each measured request to reduce reuse of a previous question prefix. Alternate index order. Warm-up excluded from measurements; no fixed seed. Small paired sample, not statistical proof.','rows':[]}
    original=rag.prepare_evidence
    trace=[]
    def record(*args,**kwargs):
        result=original(*args,**kwargs);trace.append({'passages':result[3],'prompt_characters':len(result[0] or '')});return result
    rag.prepare_evidence=record
    for repeat in range(a.repeats):
        modes=[('baseline',baseline),('trial',trial)]
        if repeat%2:modes.reverse()
        for case in cases:
            for mode,collection in modes:
                rag.collection=collection
                rag.llm.complete('Reply with OK.')
                trace.clear();start=perf_counter();first=None;final=None
                for event in rag.stream_question(case['question'],course=case['course']):
                    if event['type']=='delta' and first is None:first=perf_counter()-start
                    if event['type']=='done':final=event
                if final is None:raise RuntimeError('Missing completion')
                report['rows'].append({'case':case,'repeat':repeat+1,'mode':mode,'wall_seconds':perf_counter()-start,'first_text_seconds':first,'answer':final['answer'],'timings':final.get('timings',{}),'context_trace':list(trace)})
                a.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
                print(case['id'],repeat+1,mode,round(report['rows'][-1]['wall_seconds'],1),flush=True)


if __name__=='__main__':main()
