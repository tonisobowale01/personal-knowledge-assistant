# Cleanup review — October 28, 2026

## Completed organization

- Renamed the visible product from Ash PKA to Ash.
- Split the frontend into `index.html`, `styles.css`, and `app.js`; removed the obsolete 640px mobile prototype and CSS-generated empty-state copy. Retained the current 760px layout, native desktop/course-button mobile selection, local SVG icons, and Live Preview no-reload safeguard.
- Moved maintained and historical guides into `docs/`. Kept the baseline and focused retrieval summaries in `evaluation/` with a new evaluation entry point.
- Updated frontend checks to load the real external script and verify the CSS/script links. Retained the existing behavior checks.
- Preserved the raw benchmark reports, fixtures, reference code, application data, model/index settings, and root evaluation tools at their original locations.
- Added an ignored `evaluation/private/` destination for future raw evidence.

No application data, generated reports, or exploratory scripts were deleted. No commit or push was made. The guides are records of different development stages; historical experimental instructions are not all current product behavior.

## Candidate files for a later removal decision

These are review candidates, not permission to delete them:

| Files | Finding and recommendation |
| --- | --- |
| `test_chroma.py` | Commented-out exploratory code; no active checks. Candidate for removal after you approve. |
| `test_embedding.py` | Live embedding similarity experiment, outside the automated suite. Keep if useful for explaining embeddings; otherwise archive after approval. |
| `test_pdf_load.py` | Live PDF-extraction probe with a fixed local filename and source-text printing. Keep privately for debugging or archive after approval. |
| `app/test_ollama.py` | Early model probe. Review before running; it is not part of `unittest discover -s tests`. Preserve pending a separate decision. |
| `experiments/previous_*.py`, `original_ingest_notes.py` | Historical implementation snapshots. Preserve alongside comparison tools; do not treat them as duplicate disposable application files. |
| Root `answer_*`, `baseline_*`, `chunking_*`, `compact_*`, `top_k_*`, and related generated reports | Can contain evidence and private excerpts. Leave untouched while references and evaluation claims depend on them. Potential future archive, not deletion. |
| `chunking_trial_db/`, `chunking_trial_db_v2/` | Ignored experimental indexes, unused by normal startup. May support historical reproduction. Preserve until a backup/space-cleanup decision. |
| `.run/` | Live logs, process records, and useful acceptance evidence. Do not remove wholesale while services run. |

The root still contains local generated files because historical scripts reference their paths. Moving them without updating those tools would break reproducibility. Public Git views are cleaner because these outputs are ignored.

## Protected data

Leave `.env`, `data/notes/`, `chat_history.db` and SQLite sidecars, `chroma_db/`, `.venv/`, and the frozen baseline evidence intact. Stop the application before any future data backup or deletion. Keep the three data stores together when backing up.
