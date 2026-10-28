# Ash

A local study assistant for PDF and text notes. Upload documents under a course, ask questions, continue saved conversations, and open the original notes from retrieved sources.

Ash is a single-user local prototype built with FastAPI, Ollama, ChromaDB, LlamaIndex, SQLite, and a responsive HTML/CSS/JavaScript frontend. No cloud model or API key is required for normal use. Answers can be incomplete or incorrect; check important claims against the original notes.

## Run locally

Open Ollama, then open PowerShell in the project folder:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Start-Ash.ps1
```

The helper checks the models, starts the backend and frontend on localhost, and opens [Ash](http://127.0.0.1:3000). Repeated startup reuses healthy services. It does not reinstall packages, download models, or reindex notes.

To stop the helper-managed services:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Stop-Ash.ps1
```

Stopping leaves Ollama and saved data in place. Closing the startup console alone does not stop background services. After backend edits, stop and restart Ash. Runtime logs in `.run/` may contain questions or source excerpts.

If you prefer separate terminals, activate `.venv` and run `uvicorn app.main:app --reload` for the backend. Serve the frontend on port 3000 using `python -m http.server 3000 --bind 127.0.0.1 --directory frontend`. VS Code Live Preview can instead serve `/frontend/index.html` on port 3000. The page retains `data-server-no-reload` to protect in-progress streams from database-triggered reloads. Refresh manually after frontend edits.

## First-time setup

Install Python and Ollama. The previous local acceptance environment used Python 3.14.6 and Ollama 0.40.6 on Windows; a clean-machine installation is not yet verified.

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
ollama pull llama3.2:3b
ollama pull nomic-embed-text
```

Installing packages and downloading models requires internet access. Normal questions and document previews use local services. `requirements.txt` pins direct dependencies, not the full dependency tree. Node.js is needed only for frontend checks.

## Use Ash

1. Open the sidebar and choose a PDF or `.txt` file under **Upload notes**. Expand **Course & upload**, select or add a course, and choose **Upload**. Keep the page open until processing finishes.
2. Choose a **Search scope** on mobile, or a course in the desktop header. **All courses** searches across your notes.
3. Type a question and use the send button or Enter. The first question creates a saved chat. Searching and answer-preparation indicators appear before streamed text begins.
4. Continue with follow-up questions or reopen a saved chat. **New chat** starts a separate conversation. Rename and delete controls are beside saved chats; mobile uses pencil and trash icons.
5. Expand **Show sources** after a new answer, or use **Preview** in **Your notes**. On mobile, the bottom **Documents** button opens the library.

The original filename identifies a document. Uploading another file with the same name replaces its indexed content. Documents placed directly in `data/notes/` are not automatically indexed: upload through the application when starting with an empty index. Scanned PDFs require OCR elsewhere first.

## Architecture

```text
Browser (frontend/index.html + styles.css + app.js)
  -> FastAPI (app/main.py)
     -> PDF/text ingestion -> structural chunks -> Ollama embeddings -> ChromaDB
     -> question + course + bounded history -> retrieval -> Ollama answer stream
     -> SQLite chat persistence and on-demand original-document previews
```

Retrieval makes one embedding call and one semantic search over up to 20 candidates, then selects five full passages using a lightweight heading-overlap hint. Follow-ups use a bounded user-topic anchor. Answers are generated with `llama3.2:3b`; embeddings use `nomic-embed-text`. There is no separate lexical index, learned reranker, or model training step.

## Evaluation

The historical October 14 baseline completed 20 development questions. Assistant review against the reference notes marked **14/20** as meeting all content criteria. Median retrieval was **0.11 seconds**; for 17 answerable cases, median first text was **35.5 seconds** and median completion was **43.2 seconds**.

These results describe that configuration and corpus, not the current application's general accuracy. They are a small, non-independent development review with uncontrolled caching and warm-up effects. Later focused retrieval checks are separate evidence; they do not establish a new overall accuracy score or speed improvement.

See [evaluation](evaluation/README.md) for the method, evidence inventory, reproduction instructions, and limits. Full local reports contain document excerpts and remain ignored by Git.

## Known limitations

- Correct retrieval does not guarantee a correct answer. The model can omit facts, mix nearby concepts, or invent explanations. The Wagner-theatre relationship case remains unresolved; SJF answers can be incomplete.
- Sources identify retrieved passages, not independently verified support for every claim. Refusals may still list unrelated retrieved pages. Reopening chats restores messages, but not historical source disclosures or timings.
- Follow-up context and heading hints are heuristics. Ambiguous references may need the topic name spelled out.
- CPU-only generation may take tens of seconds or over a minute. Streaming does not remove prompt-processing time; performance varies with prompt length and caching.
- Scanned pages, diagrams, and complex PDF layouts may not yield useful text. Very long inputs are not covered by a complete token-budget guard.
- Upload replacement and index updates are not one transaction. Keep originals; a failed replacement may require retrying a valid file.
- Ash has no login and is intended for one local user. Public hosting and multi-user concurrency have not been validated.

## Project layout and data

| Path | Purpose |
| --- | --- |
| `app/`, `ingest_notes.py`, `chat_db.py` | Application backend, ingestion, and chat storage |
| `frontend/` | HTML structure, CSS styling, JavaScript behavior, and icon license |
| `tests/` | Automated checks and development question fixtures |
| `evaluation/` | Readable results and evaluation entry point |
| `benchmarks/` | Frozen reference implementations and revision metadata |
| `experiments/` | Historical development tools; not run during normal startup |
| `docs/` | Feature guides, historical decisions, release notes, and cleanup review |
| Root `evaluate_*.py`, `benchmark_*.py` | Evaluation tools; run deliberately from the project root |
| `data/notes/`, `chroma_db/`, `chat_history.db` | Private uploaded originals, search index, and saved chats |
| `.run/`, trial indexes, generated reports | Ignored local runtime and experiment output |

Stop Ash before backing up originals, the search index, and chat database together. Do not reindex as a routine startup step. Existing raw reports remain at their original paths because historical scripts reference them. See [cleanup review](docs/CLEANUP_REVIEW.md) before removing development files.

## Checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
node tests/test_frontend.cjs
node tests/test_navigation.cjs
```

Backend flow checks use isolated data and mocked generation. Frontend checks simulate the DOM and API responses; they do not replace browser testing or measure generated-answer correctness. Historical acceptance details are in [release notes](docs/V1_RELEASE.md). The October 28 cleanup reorganizes presentation and documentation without changing retrieval, prompts, models, or ingestion.

## Git hygiene

Commit application code, tests, guides, selected evaluation summaries, and startup scripts. Keep `.env`, personal notes, chats, vector indexes, runtime logs, and raw answer traces out of Git. Review explicit file selections and the staged diff before committing. See [the evaluation privacy boundary](evaluation/README.md#what-to-share).
