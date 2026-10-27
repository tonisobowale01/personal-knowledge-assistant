"""Bounded final acceptance: three fresh questions, previews and read-only app state."""
import hashlib,json
from pathlib import Path
from time import perf_counter
import httpx

ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'.run/v1_final_check.json'
out.parent.mkdir(exist_ok=True)
report={'date':'2026-10-27','rows':[],'checks':[],
        'scope':'Final verification only: three fresh-context questions, no saved-chat writes, uploads or tuning. Manual answer review required.'}
def save():out.write_text(json.dumps(report,indent=2),encoding='utf-8')
with httpx.Client(base_url='http://127.0.0.1:8000',timeout=240) as client:
    def get(path):
        response=client.get(path);response.raise_for_status();return response.json()
    before=get('/chats')['chats']
    courses=get('/courses')['courses']
    assert 'Operating Systems' in courses
    docs=get('/documents')['documents']
    for suffix in ['.pdf','.txt']:
        file=next(d['file'] for d in docs if d['file'].lower().endswith(suffix))
        from urllib.parse import quote
        response=client.get('/documents/'+quote(file,safe='')+'/preview',headers={'Range':'bytes=0-31'})
        assert response.status_code==206
        with (ROOT/'data/notes'/file).open('rb') as original:assert response.content==original.read(32)
    report['checks'].append('PDF/text preview ranges match original bytes')
    response=client.options('/ask/stream',headers={'Origin':'http://127.0.0.1:3000','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'content-type'})
    assert response.status_code==200 and response.headers.get('access-control-allow-origin')=='http://127.0.0.1:3000'
    report['checks'].append('Frontend-origin streaming preflight accepted')
    save()
    for question in ['What are the conditions for deadlocks to happen?',
                     'What four conditions are necessary for deadlock to happen?',
                     'Deadlock necessary conditions?']:
        started=perf_counter();first=None;parts=[];events=[];done=None
        row={'question':question,'course':'Operating Systems','history':[],'quality_review':None}
        try:
            with client.stream('POST','/ask/stream',json={'question':question,'course':'Operating Systems','history':[]}) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line.strip():continue
                    event=json.loads(line);events.append(event['type'])
                    if event['type']=='error':raise RuntimeError(event['message'])
                    if event['type']=='delta':
                        if first is None:first=perf_counter()-started
                        parts.append(event['text'])
                    if event['type']=='done':
                        assert done is None
                        done=event
            assert done and ''.join(parts)==done['answer']
            row.update(status='completed',answer=done['answer'],sources=done['sources'],timings=done.get('timings',{}))
        except Exception as error:row.update(status='error',answer=''.join(parts),error=str(error))
        row.update(events=events,delta_count=len(parts),first_text_seconds=first,wall_seconds=perf_counter()-started)
        report['rows'].append(row);save()
        print(json.dumps(row),flush=True)
    assert get('/chats')['chats']==before
    report['checks'].append('Saved chat list unchanged')
report['code_sha256']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['app/main.py','app/rag.py','app/retrieval.py','frontend/index.html']}
save()
