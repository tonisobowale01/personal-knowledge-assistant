"""Archived experiment; not the active baseline. Compare legacy/new retrieval on source-labelled local notes; does not generate answers."""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from statistics import mean
import chromadb
import ollama
from experiments.previous_retrieval import retrieve, DEFAULT_DISTANCE_LIMIT, compact_passages

ROOT = Path(__file__).resolve().parent

def score(case, passages):
    if not case['answerable']:
        return not passages
    matches = [any(p['metadata'].get('file_name') == source['file'] and
                   (source.get('page') is None or str(p['metadata'].get('page_label')) == source['page'])
                   for p in passages) for source in case['expected_sources']]
    return any(matches) if case.get('match') == 'any' else all(matches)

def compact(result):
    return {**result, 'candidates': [{k:v for k,v in p.items() if k != 'text'} for p in result['candidates']],
            'passages': [{k:v for k,v in p.items() if k != 'text'} for p in result['passages']]}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--db',type=Path,default=ROOT/'chroma_db')
    parser.add_argument('--output',type=Path,default=ROOT/'retrieval_report.json')
    parser.add_argument('--cases',type=Path,default=ROOT/'tests/retrieval_cases.json')
    args=parser.parse_args()
    collection=chromadb.PersistentClient(path=str(args.db)).get_collection('test_notes')
    config=collection.configuration
    metric=(config.get('hnsw') or config.get('spann') or {}).get('space')
    if metric != 'l2':
        raise RuntimeError(f'Existing 1.1 cutoff is for L2; collection uses {metric}. Calibrate separately.')
    client=ollama.Client(timeout=120)
    embeddings={}
    def embed(query):
        if query not in embeddings:
            embeddings[query]=client.embed(model='nomic-embed-text',input=query)['embeddings'][0]
        return embeddings[query]
    def complete(prompt):
        return SimpleNamespace(text=client.generate(model='llama3.2:3b',prompt=prompt,options={'temperature':0})['response'])
    cases=json.loads(args.cases.read_text())
    rows=[]
    for case in cases:
        history=[SimpleNamespace(**m) for m in case['history']]
        row={'case':case}
        for mode in ['legacy','improved']:
            result=retrieve(case['question'],case['course'],history,collection,embed,complete,distance_limit=1.1 if mode=='legacy' else DEFAULT_DISTANCE_LIMIT,legacy=mode=='legacy')
            if mode == 'improved':
                result['passages'] = compact_passages(result['queries'][0], result['passages'])
            row[mode]={**compact(result),'passed':score(case,result['passages'])}
        rows.append(row)
        # Save partial results so interruption does not lose completed cases.
        args.output.write_text(json.dumps({'metric':metric,'rows':rows},indent=2))
        print(f"{len(rows)}/{len(cases)} {case['kind']}: legacy={row['legacy']['passed']} improved={row['improved']['passed']}",flush=True)
    summary={mode:{'passed':sum(r[mode]['passed'] for r in rows),'total':len(rows),
                  'answerable_hits':sum(r[mode]['passed'] for r in rows if r['case']['answerable']),
                  'answerable_total':sum(r['case']['answerable'] for r in rows),
                  'unsupported_rejections':sum(r[mode]['passed'] for r in rows if not r['case']['answerable']),
                  'unsupported_total':sum(not r['case']['answerable'] for r in rows),
                  'mean_seconds':mean(r[mode]['seconds'] for r in rows)} for mode in ['legacy','improved']}
    args.output.write_text(json.dumps({'metric':metric,'summary':summary,'rows':rows,
        'limitations':'Small development set; source presence does not establish passage completeness or answer accuracy. Original-query embeddings are cached across modes; timings are diagnostic, not a fair latency benchmark. Legacy cutoff is 1.1; improved cutoff is 1.0, selected on this development set, not a held-out test.'},indent=2))
    print(json.dumps(summary,indent=2))

if __name__=='__main__': main()
