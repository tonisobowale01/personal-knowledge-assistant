"""Actual answer baseline with manual quality review; no automatic correctness score."""
import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parent

def write_review(report,path):
 lines=['# Answer-quality review','', 'Quality ratings require review against the reference notes. Matching words or source pages does not establish correctness.','']
 lines+=['| Case | Complete | Supported | Missing evidence | Seconds |','|---|---|---|---|---:|']
 for row in report['rows']:
  rating=row['quality_review']
  lines.append(f"| {row['case']['id']} | {rating.get('completeness')} | {rating.get('supported_claims')} | {rating.get('missing_evidence')} | {row.get('wall_seconds',0):.1f} |")
 lines+=['',report.get('review_method','Ratings are pending review.'),'']
 for row in report['rows']:
  case=row['case'];lines += [f"## {case['id']}: {case['question']}",'',f"Category: {case['kind']} | Status: {row['status']}",f"First text: {row.get('first_text_seconds')} s | Completion: {row.get('wall_seconds')} s",'', 'Expected points:']
  lines += ['- '+point for point in case['expected_points']]
  if case['reference_sources']:
   links=[]
   for ref in case['reference_sources']:
    label=ref['file']+(f" (page {ref['page']})" if ref['page'] else '')
    target=(ROOT/'data/notes'/ref['file']).as_posix()
    links.append(f'[{label}](<{target}>)')
   lines+=['','Reference notes: '+', '.join(links)]
  if case['unsupported_claims_to_check']: lines+=['','Check for unsupported claims:']+['- '+point for point in case['unsupported_claims_to_check']]
  lines+=['','Actual answer:','',row.get('answer') or '(No completed answer)', '', f"Review: completeness {row['quality_review'].get('completeness')} | supported claims {row['quality_review'].get('supported_claims')} | missing evidence {row['quality_review'].get('missing_evidence')}", row['quality_review'].get('notes',''),'']
 path.write_text('\n'.join(lines),encoding='utf-8')

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--ids',nargs='*');parser.add_argument('--cases',type=Path,default=ROOT/'tests/answer_cases.json');parser.add_argument('--output',type=Path,default=ROOT/'answer_baseline.json');parser.add_argument('--resume',action='store_true');args=parser.parse_args()
 from app.rag import stream_question,collection,llm
 from app import rag
 original_prepare=rag.prepare_evidence
 trace=[]
 def record_prepare(*a,**kw):
  result=original_prepare(*a,**kw)
  trace.append({"question":a[0] if a else kw.get("question"),"resolved_question":result[4],"prompt_characters":len(result[0] or ""),"passages":result[3]})
  return result
 rag.prepare_evidence=record_prepare
 cases=json.loads(args.cases.read_text(encoding='utf-8'))
 if args.ids:
  unknown=set(args.ids)-{c['id'] for c in cases}
  if unknown:parser.error(f'Unknown IDs: {unknown}')
  cases=[c for c in cases if c['id'] in args.ids]
 report=json.loads(args.output.read_text(encoding='utf-8')) if args.resume and args.output.exists() else {'rows':[], 'limitations':'Small development baseline, not a held-out test. Ratings are manual and pending; no overall accuracy score. Timings include cold/warm effects and are not a controlled comparison.'}
 current_hashes={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['app/rag.py','app/retrieval.py']}
 if args.resume and report.get('code_sha256') and report['code_sha256'] != current_hashes:
  raise RuntimeError('Application code changed; use a new output file instead of mixing baselines')
 current_fixture=hashlib.sha256(args.cases.read_bytes()).hexdigest()
 if args.resume and report.get('fixture_sha256') and report['fixture_sha256'] != current_fixture:
  raise RuntimeError('Reference cases changed; start a new baseline')
 report['fixture_sha256']=current_fixture
 report['fixture_path']=str(args.cases.resolve())
 done={r['case']['id'] for r in report['rows']};report['total_cases']=len(json.loads(args.cases.read_text(encoding='utf-8')))
 corpus=collection.get(include=['documents','metadatas'])
 corpus_rows=sorted(zip(corpus['ids'],corpus['documents'],corpus['metadatas']),key=lambda item:item[0])
 corpus_hash=hashlib.sha256(json.dumps(corpus_rows,sort_keys=True).encode()).hexdigest()
 if args.resume and report.get('corpus_sha256') and report['corpus_sha256'] != corpus_hash:
  raise RuntimeError('Indexed corpus changed; start a new baseline')
 report['corpus_sha256']=corpus_hash
 references={}
 for case in cases:
  for reference in case['reference_sources']:
   key=reference['file']+':'+str(reference['page'])
   if key in references:continue
   data=collection.get(where={'file_name':reference['file']},include=['documents','metadatas'])
   texts=[text for text,meta in zip(data['documents'],data['metadatas']) if meta.get('page_label')==reference['page']]
   if not texts:raise RuntimeError(f'Missing reference evidence: {key}')
   text='\n\n'.join(texts)
   references[key]={**reference,'text':text,'sha256':hashlib.sha256(text.encode()).hexdigest()}
 report['reference_evidence']=references
 current_model={'name':llm.model,'context_window':llm.context_window,'temperature':llm.temperature,'system_prompt':llm.system_prompt,'request_timeout':llm.request_timeout}
 if args.resume and report.get('model') and report['model'] != current_model:
  raise RuntimeError('Model settings changed; start a new baseline')
 if args.resume and report.get('reference_evidence'):
  for key,value in report['reference_evidence'].items():
   if key in references and references[key]['sha256'] != value['sha256']:
    raise RuntimeError('Reference notes changed; start a new baseline')
 report['model']=current_model
 report['code_sha256']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['app/rag.py','app/retrieval.py']}
 for case in cases:
  if case['id'] in done:continue
  trace.clear()
  start=perf_counter();first=None;parts=[];final=None;row={'case':case,'quality_review':{'completeness':None,'supported_claims':None,'missing_evidence':None},'status':'running'}
  try:
   for event in stream_question(case['question'],course=case['course'],history=[SimpleNamespace(**m) for m in case['history']]):
    if event['type']=='delta':
     if first is None:first=perf_counter()-start
     parts.append(event['text'])
    if event['type']=='done':final=event
   if final is None:raise RuntimeError('No completion event')
   row.update(status='completed',answer=final['answer'],sources=final['sources'],timings=final.get('timings',{}))
  except Exception as exc:row.update(status='error',answer=''.join(parts),error=str(exc))
  row.update(first_text_seconds=first,wall_seconds=perf_counter()-start,context_trace=list(trace))
  report['rows'].append(row)
  args.output.write_text(json.dumps(report,indent=2),encoding='utf-8');write_review(report,args.output.with_suffix('.md'))
  print(f"{case['id']} {row['status']} {row['wall_seconds']:.1f}s",flush=True)
 print('Completed cases:',len(report['rows']),'Quality ratings remain pending review.',flush=True)

if __name__=='__main__':main()
