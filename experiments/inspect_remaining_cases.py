"""Read-only evidence comparison for the user's deadlock/theatre failures."""
import hashlib,json,sqlite3,sys
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app import rag
from app.retrieval import retrieve

questions=[('deadlock_natural','what are the conditions for deadlocks to happen','Operating Systems'),
 ('deadlock_four','what four conditions are necessary for deadlock to happen','Operating Systems'),
 ('deadlock_keywords','deadlock necessary conditions?','Operating Systems'),
 ('theatre','who was the one that built a special theatre for Wagner','Music'),
 ('ludwig','Who was King Ludwig','Music')]
db=sqlite3.connect(ROOT/'chat_history.db')
rows=[];memo={}
def embed(q):
    if q not in memo:memo[q]=rag.ollama.embed(model='nomic-embed-text',input=q)['embeddings'][0]
    return memo[q]
for name,question,course in questions:
    found=db.execute("SELECT id,chat_id FROM message WHERE role='user' AND lower(content)=lower(?) ORDER BY id DESC LIMIT 1",(question,)).fetchone()
    hist=[]
    if found:hist=[SimpleNamespace(role=r,content=t) for r,t in db.execute('SELECT role,content FROM message WHERE chat_id=? AND id<? ORDER BY id',(found[1],found[0]))]
    row=dict(id=name,question=question,course=course,history=[vars(m) for m in hist])
    for mode,prefix in [('baseline',''),('query_prefix','search_query: ')]:
        row[mode]=retrieve(question,course,rag.collection,lambda q:embed(prefix+q),history=hist)
        print(name,mode,json.dumps({'query':row[mode]['queries'],'pages':[(p['metadata'].get('file_name'),p['metadata'].get('page_label')) for p in row[mode]['passages']]}),flush=True)
    rows.append(row)
data=rag.collection.get(include=['documents','metadatas'])
report={'rows':rows,'corpus_sha256':hashlib.sha256(json.dumps(sorted(zip(data['ids'],data['documents'],data['metadatas'])),sort_keys=True).encode()).hexdigest(),
 'protocol':'Original five passages, cutoff, corpus, history resolver and model. Trial changes only embedding query input by adding a general task prefix. No index writes or generated-answer ratings.'}
(ROOT/'.run/remaining_evidence.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
for row in rows:
    if row['id'] in ['theatre','deadlock_natural']:
        for mode in ['baseline','query_prefix']:
            print('EVIDENCE',row['id'],mode,json.dumps([p['text'] for p in row[mode]['passages']]),flush=True)
