import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
rag = types.ModuleType('app.rag')
rag.ask_question = Mock(return_value={'answer': 'Saved answer', 'sources': []})
rag.stream_question = Mock()
for name in ['get_courses', 'get_documents', 'delete_document']:
    setattr(rag, name, Mock(return_value=[]))
sys.modules['app.rag'] = rag
ingest = types.ModuleType('ingest_notes')
ingest.ingest_file = Mock()
sys.modules['ingest_notes'] = ingest
import chat_db
from app.main import app
import app.main as main
from fastapi.testclient import TestClient

class Chats(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        chat_db.DB_PATH = Path(self.temp.name) / 'test.db'
        self.original_notes_dir = main.NOTES_DIR
        main.NOTES_DIR = Path(self.temp.name) / 'notes'
        main.NOTES_DIR.mkdir()
        rag.ask_question.reset_mock(side_effect=True)
        rag.stream_question.reset_mock(side_effect=True)
        self.client = TestClient(app)
        self.client.__enter__()
    def tearDown(self):
        self.client.__exit__(None, None, None)
        main.NOTES_DIR = self.original_notes_dir
        self.temp.cleanup()
    def test_create_continue_reopen_and_isolate(self):
        first = self.client.post('/chats', json={'title': 'First', 'course': 'OS'}).json()['id']
        second = self.client.post('/chats', json={'title': 'Second'}).json()['id']
        for question in ['One', 'Two']:
            self.assertEqual(self.client.post('/ask', json={'question': question, 'chat_id': first, 'history': [{'role':'user','content':'Wrong chat'}]}).status_code, 200)
        history = rag.ask_question.call_args.kwargs['history']
        self.assertEqual([m.content for m in history], ['One', 'Saved answer'])
        self.assertEqual(len(self.client.get(f'/chats/{first}/messages').json()['messages']), 4)
        self.assertEqual(self.client.get(f'/chats/{second}/messages').json()['messages'], [])
        with TestClient(app) as reopened:
            self.assertEqual(len(reopened.get(f'/chats/{first}/messages').json()['messages']), 4)
            self.assertEqual(len(reopened.get('/chats').json()['chats']), 2)
    def test_generation_failure_leaves_no_partial_turn(self):
        cid = self.client.post('/chats', json={'title':'Failure'}).json()['id']
        rag.ask_question.side_effect = RuntimeError('Ollama unavailable')
        with self.assertRaises(RuntimeError):
            self.client.post('/ask', json={'question':'Try', 'chat_id':cid})
        self.assertEqual(chat_db.get_messages(cid), [])
    def test_missing_chat_is_rejected(self):
        self.assertEqual(self.client.get('/chats/999/messages').status_code, 404)
        self.assertEqual(self.client.post('/ask', json={'question':'Try', 'chat_id':999}).status_code, 404)
        rag.ask_question.assert_not_called()
    def test_exchange_rolls_back_and_foreign_keys_enforced(self):
        cid = chat_db.create_chat('Atomic')
        with self.assertRaises(Exception):
            chat_db.add_exchange(cid, 'Question', None)
        self.assertEqual(chat_db.get_messages(cid), [])
        with self.assertRaises(Exception):
            chat_db.add_message(999, 'user', 'Orphan')

    def test_rename_preserves_messages_and_course(self):
        cid = chat_db.create_chat('Original', 'OS')
        chat_db.add_exchange(cid, 'Question', 'Answer')
        response = self.client.patch(f'/chats/{cid}', json={'title': '  Renamed  '})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['title'], 'Renamed')
        self.assertEqual(chat_db.get_chat(cid), (cid, 'Renamed', 'OS'))
        self.assertEqual(len(chat_db.get_messages(cid)), 2)
        for title in ['', '   ', '\t']:
            self.assertEqual(self.client.patch(f'/chats/{cid}', json={'title': title}).status_code, 422)
        self.assertEqual(chat_db.get_chat(cid)[1], 'Renamed')
        self.assertEqual(self.client.patch('/chats/999', json={'title':'Missing'}).status_code, 404)

    def test_delete_removes_only_selected_chat_and_messages(self):
        cid = chat_db.create_chat('Delete')
        keep = chat_db.create_chat('Keep')
        chat_db.add_exchange(cid, 'Deleted question', 'Deleted answer')
        chat_db.add_exchange(keep, 'Kept question', 'Kept answer')
        self.assertEqual(self.client.delete(f'/chats/{cid}').status_code, 200)
        self.assertIsNone(chat_db.get_chat(cid))
        self.assertEqual(chat_db.get_messages(cid), [])
        self.assertEqual(len(chat_db.get_messages(keep)), 2)
        self.assertEqual(self.client.get(f'/chats/{cid}/messages').status_code, 404)
        self.assertEqual(self.client.delete(f'/chats/{cid}').status_code, 404)
        with TestClient(app) as reopened:
            self.assertEqual([chat['id'] for chat in reopened.get('/chats').json()['chats']], [keep])

    def test_preview_pdf_text_and_partial_requests(self):
        pdf = b'%PDF-1.7\npreview fixture'
        (main.NOTES_DIR / 'Notes with spaces.pdf').write_bytes(pdf)
        (main.NOTES_DIR / 'sample.txt').write_text('Plain text <script>example</script>')
        response = self.client.get('/documents/Notes%20with%20spaces.pdf/preview')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, pdf)
        self.assertEqual(response.headers['content-type'], 'application/pdf')
        self.assertIn('inline', response.headers['content-disposition'])
        self.assertEqual(response.headers['x-content-type-options'], 'nosniff')
        response = self.client.get('/documents/Notes%20with%20spaces.pdf/preview', headers={'Range':'bytes=0-7'})
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response.content, pdf[:8])
        self.assertIn('bytes 0-7/', response.headers['content-range'])
        response = self.client.get('/documents/sample.txt/preview')
        self.assertTrue(response.headers['content-type'].startswith('text/plain'))
        self.assertIn('<script>', response.text)
        rag.ask_question.assert_not_called()

    def test_preview_missing_unsupported_and_path_escape(self):
        self.assertEqual(self.client.get('/documents/missing.pdf/preview').status_code, 404)
        (main.NOTES_DIR / 'unsafe.html').write_text('<script>alert(1)</script>')
        self.assertEqual(self.client.get('/documents/unsafe.html/preview').status_code, 415)
        self.assertEqual(self.client.get('/documents/..%5Ctest.db/preview').status_code, 400)
        self.assertEqual(self.client.get('/documents/C%3A%5Coutside.pdf/preview').status_code, 400)
        self.assertEqual(self.client.get('/documents/.gitkeep/preview').status_code, 404)
        rag.ask_question.assert_not_called()

    def test_stream_saves_once_and_uses_database_history(self):
        import json
        cid = chat_db.create_chat('Stream')
        chat_db.add_exchange(cid, 'Earlier', 'Earlier answer')
        def output(*args, **kwargs):
            yield {'type':'status','message':'Searching'}
            yield {'type':'delta','text':'Saved '}
            yield {'type':'delta','text':'answer'}
            self.assertEqual(len(chat_db.get_messages(cid)), 2)
            yield {'type':'done','answer':'Saved answer','sources':[]}
        rag.stream_question.side_effect = output
        response=self.client.post('/ask/stream',json={'question':'Next','chat_id':cid,'history':[{'role':'user','content':'Wrong'}]})
        events=[json.loads(line) for line in response.text.splitlines()]
        self.assertEqual(response.status_code,200)
        self.assertIn('application/x-ndjson',response.headers['content-type'])
        self.assertEqual([e['type'] for e in events],['status','delta','delta','done'])
        self.assertEqual(len(chat_db.get_messages(cid)),4)
        self.assertEqual([m.content for m in rag.stream_question.call_args.kwargs['history']],['Earlier','Earlier answer'])
        self.assertEqual(self.client.post('/ask/stream',json={'question':'Next','chat_id':999}).status_code,404)

    def test_failed_stream_does_not_save_partial_exchange(self):
        import json
        cid=chat_db.create_chat('Failed stream')
        def output(*args, **kwargs):
            yield {'type':'delta','text':'Partial'}
            raise RuntimeError('Model unavailable')
        rag.stream_question.side_effect=output
        with self.assertLogs('uvicorn.error',level='ERROR'):
            response=self.client.post('/ask/stream',json={'question':'Next','chat_id':cid})
        events=[json.loads(line) for line in response.text.splitlines()]
        self.assertEqual(events[-1]['type'],'error')
        self.assertEqual(chat_db.get_messages(cid),[])

    def test_upload_finishes_ingestion_in_worker_before_acknowledging(self):
        import asyncio
        def process(path, course):
            self.assertEqual(path.read_bytes(),b'Sample notes')
            self.assertEqual(course,'Test course')
            with self.assertRaises(RuntimeError):
                asyncio.get_running_loop()
            return 2
        previous=main.ingest_file.side_effect
        main.ingest_file.side_effect=process
        try:
            response=self.client.post('/upload',files={'file':('sample.txt',b'Sample notes','text/plain')},data={'course':'Test course'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['chunks_stored'],2)
        finally:
            main.ingest_file.side_effect=previous

    def test_real_http_delivers_delta_before_completion(self):
        import json
        import socket
        import threading
        import time
        import urllib.request
        import uvicorn
        cid=chat_db.create_chat('Wire test')
        finish=threading.Event()
        def output(*args, **kwargs):
            yield {'type':'delta','text':'First words'}
            if not finish.wait(5): raise RuntimeError('Test did not release completion')
            yield {'type':'done','answer':'First words','sources':[]}
        rag.stream_question.side_effect=output
        sock=socket.socket();sock.bind(('127.0.0.1',0));sock.listen()
        port=sock.getsockname()[1]
        server=uvicorn.Server(uvicorn.Config(app,log_level='error'))
        worker=threading.Thread(target=server.run,kwargs={'sockets':[sock]},daemon=True)
        worker.start()
        try:
            deadline=time.monotonic()+5
            while not server.started and time.monotonic()<deadline: time.sleep(.01)
            self.assertTrue(server.started)
            req=urllib.request.Request(f'http://127.0.0.1:{port}/ask/stream',
                data=json.dumps({'question':'Next','chat_id':cid}).encode(),headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=5) as response:
                self.assertEqual(json.loads(response.readline())['text'],'First words')
                self.assertFalse(finish.is_set())
                self.assertEqual(chat_db.get_messages(cid),[])
                finish.set()
                self.assertEqual(json.loads(response.readline())['type'],'done')
            self.assertEqual(len(chat_db.get_messages(cid)),2)
        finally:
            finish.set();server.should_exit=True;worker.join(timeout=5);sock.close()

if __name__ == '__main__': unittest.main()
