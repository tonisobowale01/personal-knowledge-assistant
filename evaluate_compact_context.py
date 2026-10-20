"""Archived experiment; not the active baseline. Replay compact answer contexts against a saved source-labelled retrieval report."""
import json
from pathlib import Path
import chromadb
from experiments.previous_retrieval import compact_passages
from evaluate_retrieval import score
ROOT=Path(__file__).resolve().parent

def main():
 collection=chromadb.PersistentClient(path=str(ROOT/'chroma_db')).get_collection('test_notes')
 report=json.loads((ROOT/'retrieval_report.json').read_text())
 rows=[]
 for row in report['rows']:
  old=row['improved']['passages'];ids=[p['id'] for p in old]
  data=collection.get(ids=ids,include=['documents']) if ids else {'ids':[],'documents':[]}
  texts=dict(zip(data['ids'],data['documents']))
  passages=[dict(p,text=texts[p['id']]) for p in old]
  selected=compact_passages(row['improved']['queries'][0],passages)
  rows.append({'question':row['case']['question'],'passed':score(row['case'],selected),
   'before_characters':sum(len(p['text']) for p in passages),'after_characters':sum(len(p['text']) for p in selected),
   'sources':[p['metadata'].get('page_label') for p in selected]})
 output={'rows':rows,'limitations':'Saved-candidate replay only; source presence does not prove answer accuracy or speed improvement. Requires matching current indexed documents.'}
 (ROOT/'compact_report.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
 print(json.dumps({'passed':sum(r['passed'] for r in rows),'total':len(rows),'comparison':rows[4]}))

if __name__=='__main__':main()
