"""Attach explicit manual review notes and source snapshots to a completed baseline."""
import argparse
import hashlib
import json
from pathlib import Path
import chromadb
from evaluate_answers import write_review
ROOT=Path(__file__).resolve().parent

def main():
 p=argparse.ArgumentParser();p.add_argument('--collection',default='test_notes');p.add_argument('--db',type=Path,default=ROOT/'chroma_db');p.add_argument('--report',type=Path,default=ROOT/'answer_baseline.json');p.add_argument('--reviews',type=Path,default=ROOT/'answer_reviews.json');args=p.parse_args()
 report=json.loads(args.report.read_text(encoding='utf-8'));reviews=json.loads(args.reviews.read_text(encoding='utf-8'))
 collection=chromadb.PersistentClient(path=str(args.db)).get_collection(args.collection)
 corpus=collection.get(include=['documents','metadatas'])
 corpus_rows=sorted(zip(corpus['ids'],corpus['documents'],corpus['metadatas']),key=lambda item:item[0])
 current_corpus=hashlib.sha256(json.dumps(corpus_rows,sort_keys=True).encode()).hexdigest()
 if report.get('corpus_sha256') and report['corpus_sha256'] != current_corpus:
  raise RuntimeError('Review database does not match the recorded corpus')
 report['corpus_sha256']=current_corpus
 references={}
 for row in report['rows']:
  if row['case']['id'] in reviews:row['quality_review']=reviews[row['case']['id']]
  for ref in row['case']['reference_sources']:
   key=ref['file']+':'+str(ref['page'])
   if key in references:continue
   data=collection.get(where={'file_name':ref['file']},include=['documents','metadatas'])
   text='\n\n'.join(t for t,m in zip(data['documents'],data['metadatas']) if m.get('page_label')==ref['page'])
   if not text:raise RuntimeError(f'Missing reference {key}')
   references[key]={**ref,'text':text,'sha256':hashlib.sha256(text.encode()).hexdigest()}
 report['reference_evidence']=references
 reviewed=[r for r in report['rows'] if r['quality_review'].get('completeness')]
 acceptable=lambda r: r['status']=='completed' and r['quality_review']['completeness']=='pass' and r['quality_review']['supported_claims']=='pass' and r['quality_review']['missing_evidence'] in ['pass','not_applicable']
 report['review_summary']={'completed':sum(r['status']=='completed' for r in report['rows']),'reviewed':len(reviewed),'met_review_criteria':sum(acceptable(r) for r in reviewed),'flagged_ids':[r['case']['id'] for r in reviewed if not acceptable(r)]}
 report['review_method']='Assistant review against expected answer points and supplied reference notes; judgments are not independent human ratings.'
 fixture=Path(report.get('fixture_path',ROOT/'tests/answer_cases.json'))
 current_fixture=hashlib.sha256(fixture.read_bytes()).hexdigest()
 if report.get('fixture_sha256') and report['fixture_sha256'] != current_fixture:
  raise RuntimeError('Fixture changed since this report was generated')
 report['fixture_sha256']=current_fixture
 args.report.write_text(json.dumps(report,indent=2),encoding='utf-8');write_review(report,args.report.with_suffix('.md'))
 print('Reviewed',sum(bool(r['quality_review'].get('completeness')) for r in report['rows']),'of',len(report['rows']))

if __name__=='__main__':main()
