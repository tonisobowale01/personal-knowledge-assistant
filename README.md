# Personal Knowledge Assistant (Ash)

A local study assistant for PDF and text notes. Upload notes under a course, ask questions, continue saved conversations, and open original documents from answer sources.

Version 1 uses FastAPI, a plain HTML/JavaScript frontend, SQLite chats, ChromaDB retrieval, LlamaIndex and Ollama. No cloud model or API key is required. Answers can still contain mistakes; check important details against the previewed notes.

## Start using it on this computer

Open Ollama, open PowerShell in this project folder, then run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Start-Ash.ps1
```

This checks the models, starts the backend and frontend in the background, and opens **http://127.0.0.1:3000**. Running it again reuses healthy services. It does not reinstall packages, download models or reingest notes.

To stop Ash:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Stop-Ash.ps1
```

Stopping leaves Ollama and saved data in place. After changing backend code, stop Ash and start it again. Closing the startup console alone does not stop background services. Logs are in `.run/backend.stderr.log` and `.run/frontend.stderr.log`; they can contain question text.

## One-time setup on another Windows computer

Use Python 3.14 and Ollama. This release was checked with Python 3.14.6 and Ollama 0.40.6 on Windows; a clean-machine installation has not been verified. From the project folder:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

Package installation and initial model downloads need internet access. Normal answering and previews use local services. Open Ollama before starting Ash. The dependency file pins direct packages from the tested environment; it is not a complete transitive lockfile.

Start Ash, then choose a PDF or `.txt` file in **Upload Notes**, choose or add a course, and click **Upload**. Files in `data/notes` are not automatically indexed on startup; upload them through the app if starting with an empty index. Use text-based PDFs; scanned pages need OCR elsewhere first.

## Everyday use

1. Select a course, or leave **All courses** selected.
2. Enter a question and click **Ask**. The first question creates a saved chat. Text appears as the model generates it, after retrieval and prompt processing finish.
3. Ask follow-ups in that chat. Click a saved chat to reopen it; **New Chat** starts a separate conversation.
4. Rename or delete chats using their list controls. Deleting a chat removes its messages.
5. Use source links or **Preview** in the knowledge base to view originals. PDF links include the page when available. Reopened chats retain messages but do not restore historical source links or timings.

Select a course to narrow ambiguous questions. Rephrase vague questions with the topic name when needed. Filename is the document identity: uploading another document with the same filename replaces its indexed content rather than creating a separate document.

## Version 1 features

- Persistent chats: create, reopen, continue, rename and delete.
- Course filtering, PDF/text ingestion and persistent document chunks.
- Five-chunk semantic retrieval with a lightweight user-topic anchor for follow-ups.
- Streamed answers and retrieval/generation timing logs.
- Document listing, deletion and previews served on demand.
- Startup/shutdown helpers and automated flow checks.

## Known limitations and performance

- The model can omit facts, confuse nearby subjects or invent claims even when the correct notes are retrieved. Comparisons and questions with several parts remain less reliable. A refusal is not proof the answer is absent from the full document.
- The follow-up resolver is a small heuristic, not full language understanding. It retains the latest explicit user topic, but ambiguous references may need rephrasing.
- Retrieval ranks can be imperfect. Relevant information sometimes appears third or fourth, so five chunks remain the default. Hybrid search and reranking are not enabled.
- On the tested CPU-only laptop, fresh-prompt answers commonly take tens of seconds; longer prompts can take over a minute. Streaming cannot remove prompt-processing time. Timings vary with caching and answer length.
- Scanned/image-only PDFs, diagrams and complicated layouts may not extract useful text. Previews themselves do not invoke the model or create embeddings.
- Sources list retrieved passages, not independently verified citations for every claim. Refusals can still show retrieved source links.
- Uploads and index changes are not a single transaction. A failed replacement upload can leave source files and indexed text out of sync; keep originals and retry a valid file. Multi-user concurrency is outside this release's scope.
- This is a local single-user app without login. The startup helper binds to `127.0.0.1`; it is not a public-hosting setup.

## Your data and backups

- `data/notes/`: uploaded originals.
- `chroma_db/`: indexed chunks and embeddings; also retains the earlier benchmark backup collection.
- `chat_history.db`: saved chats and messages.
- `.run/`: runtime logs and acceptance-check output.

Stop Ash before backing up the notes folder, ChromaDB folder and chat database together. Do not rebuild the index as a routine startup step. Benchmark reports and trial indexes are development artifacts, unused by the normal app.

## Checks and release notes

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
node tests/test_frontend.cjs
```

Python tests use isolated databases and mocked generation for flow checks. Frontend checks simulate its DOM and requests; they do not replace manual browser testing. Node is needed for frontend checks, not for running Ash. See [V1_RELEASE.md](V1_RELEASE.md) for the release checklist and live-check results.

The architecture and standalone answer prompt remain the baseline. The larger prompt experiment was rejected; see [ANSWER_PROMPT_TRIAL.md](ANSWER_PROMPT_TRIAL.md). The smaller chunk-count experiments were not promoted; see [TOP_K_COMPARISON.md](TOP_K_COMPARISON.md).
