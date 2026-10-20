"""Short release smoke check against running Ash; removes only its own test chats."""
import json
import sys
from pathlib import Path
from time import perf_counter
from urllib.parse import quote
import httpx

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'.run/v1_acceptance.json'


def main():
    client=httpx.Client(base_url='http://127.0.0.1:8000',timeout=240)
    report={'checks':[],'answers':[],'created_test_chats':[],
            'limitations':'HTTP live smoke plus separately run automated flow checks. Answer quality requires manual review. No fresh-machine install or visual browser check.'}
    def save(): OUTPUT.write_text(json.dumps(report,indent=2),encoding='utf-8')
    def request(method,path,**kw):
        response=client.request(method,path,**kw);response.raise_for_status();return response
    def check(name): report['checks'].append(name);save();print(name,flush=True)
    def ask(name,body):
        started=perf_counter();first=None;deltas=[];final=None;events=[]
        with client.stream('POST','/ask/stream',json=body) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line.strip(): continue
                event=json.loads(line);events.append(event['type'])
                if event['type']=='error': raise RuntimeError(event['message'])
                if event['type']=='delta':
                    if first is None:first=perf_counter()-started
                    deltas.append(event['text'])
                if event['type']=='done':
                    assert final is None
                    final=event
        assert final is not None and ''.join(deltas)==final['answer']
        report['answers'].append(dict(id=name,request=body,answer=final['answer'],
            sources=final['sources'],timings=final.get('timings',{}),
            first_text_seconds=first,wall_seconds=perf_counter()-started,
            delta_count=len(deltas),events=events,quality_review=None))
        save();print(name,round(report['answers'][-1]['wall_seconds'],1),'seconds',flush=True)
    original_chats=request('GET','/chats').json()['chats']
    try:
        courses=request('GET','/courses').json()['courses']
        assert 'Operating Systems' in courses and 'Networking' in courses
        assert 'Personal Knowledge Assistant' in httpx.get('http://127.0.0.1:3000').text
        check('Frontend and backend healthy')
        docs=request('GET','/documents').json()['documents']
        for suffix in ['.pdf','.txt']:
            document=next(d for d in docs if d['file'].lower().endswith(suffix))
            file=document['file'];path='/documents/'+quote(file,safe='')+'/preview'
            response=request('GET',path,headers={'Range':'bytes=0-31'})
            assert response.status_code==206
            with (ROOT/'data/notes'/file).open('rb') as source:
                assert response.content==source.read(32)
            assert response.headers['content-disposition'].startswith('inline')
        check('PDF/text previews return matching source bytes and support ranges')
        for title in ['Ash v1 acceptance - temporary','Ash v1 isolation - temporary']:
            chat=request('POST','/chats',json={'title':title,'course':'Operating Systems'}).json()
            report['created_test_chats'].append(chat['id']);save()
        chat_id,other_id=report['created_test_chats']
        assert len(request('GET','/chats').json()['chats'])==len(original_chats)+2
        ask('sjf_definition',{'question':'What is SJF?','chat_id':chat_id,'course':'Operating Systems'})
        assert len(request('GET',f'/chats/{chat_id}/messages').json()['messages'])==2
        ask('saved_sjf_followup',{'question':'What are its advantages?','chat_id':chat_id,'course':'Operating Systems'})
        saved=request('GET',f'/chats/{chat_id}/messages').json()['messages']
        assert len(saved)==4 and [m['role'] for m in saved]==['user','assistant']*2
        assert saved[-1]['content']==report['answers'][-1]['answer']
        assert request('GET',f'/chats/{other_id}/messages').json()['messages']==[]
        request('PATCH',f'/chats/{chat_id}',json={'title':'Ash v1 renamed - temporary'})
        renamed=next(c for c in request('GET','/chats').json()['chats'] if c['id']==chat_id)
        assert renamed['title']=='Ash v1 renamed - temporary'
        check('Create/list/reopen/continue/rename chats; separate chats stay isolated')
        rr=[{'role':'user','content':'Explain Round Robin scheduling.'},
            {'role':'assistant','content':'It uses a fixed time quantum.'},
            {'role':'user','content':'What are its advantages?'},
            {'role':'assistant','content':'It gives each process a fair share of CPU time.'},
            {'role':'user','content':'What are its disadvantages?'},
            {'role':'assistant','content':'A very small quantum increases context-switching overhead.'}]
        ask('long_round_robin_followup',{'question':'What happens if its time quantum is too large?',
            'course':'Operating Systems','history':rr})
        star=[{'role':'user','content':'Explain star topology.'},
            {'role':'assistant','content':'It connects devices to a central hub or switch.'},
            {'role':'user','content':'What are its advantages?'},
            {'role':'assistant','content':'It is easy to manage and expand.'},
            {'role':'user','content':'And its disadvantages?'},
            {'role':'assistant','content':'It depends on the central device.'}]
        ask('long_star_followup',{'question':'What happens if that central device fails?',
            'course':'Networking','history':star})
        ask('unsupported_question',{'question':'What is photosynthesis?','course':'Operating Systems'})
        check('Five live streamed answers completed without transport errors')
    finally:
        for chat_id in report['created_test_chats']:
            request('DELETE',f'/chats/{chat_id}')
            assert client.get(f'/chats/{chat_id}/messages').status_code==404
        assert request('GET','/chats').json()['chats']==original_chats
        check('Only temporary test chats deleted; pre-existing chat list unchanged')
        client.close()


if __name__=='__main__': main()
