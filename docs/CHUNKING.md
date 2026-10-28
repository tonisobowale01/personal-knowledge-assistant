# Structural chunks during ingestion

The live index now uses the conservative structural-chunking trial. Retrieval, the original answer prompt, model settings, streaming, and timing measurements are unchanged.

## What changed

- Explicit numbered/Markdown headings and labelled definitions form boundaries. Topic sections keep their explanations and nested limitations together.
- Pages beginning with a substantial untitled explanation retain their page context. A first prototype split such a paragraph into an anonymous fragment and lost the bus definition from retrieval; that prototype was rejected.
- Split sections repeat their heading; continued Markdown tables repeat their original column header and separator. The nominal 512-token budget and 50-token overlap remain.
- Original file and page metadata are preserved for previews. A source-word coverage audit found no missing words on any page in the three test documents; this is a coverage check, not proof of semantic quality.
- Re-ingestion stores all new chunks before removing obsolete IDs for that filename. Extraction, embedding, and upsert failures are tested to avoid deleting existing chunks. Chroma upsert/delete is not a cross-operation transaction.

The index was rebuilt from the existing three source files. Live chunks increased from 47 to 52. The original 47 entries, including their vectors and metadata, were verified and backed up in the same database as collection `test_notes_baseline_20261014`. The backup is separate from ordinary queries.

## Actual answer trial

All 20 cases completed. Fresh assistant review marked 15 as meeting every criterion, versus 14 in the original baseline. This is a small development comparison, not independent proof of a general accuracy improvement.

- The bus/star comparison no longer transfers tree structure or invents star redundancy, but its closing comparison remains partly unsupported.
- The multipart answer no longer adds a blanket multicore performance claim.
- The OS answer became complete despite identical supplied context; this is model variation, not evidence for chunking.
- Clustering remains incomplete, and the symmetric-clustering comparison still overgeneralizes fault tolerance.
- SJF still invents an incorrect quote calling SRTF non-preemptive. Chunking has not solved that model error.
- FCFS omitted an explicit FIFO rule in the initial trial. In three subsequent candidate repeats it included the rule correctly. The baseline repeats also varied, including one false no-context-switching claim.
- Both follow-ups and all three missing-evidence checks passed. The six additional scope cases retained correct All courses/course behavior; SJF definitions still only expanded the acronym.

## Speed evidence

For the 17 answerable cases, median completion time was **32.7 seconds**, versus **43.2 seconds** in the frozen baseline; median time to first text was **24.2 versus 35.5 seconds**. The full trial took about **13.3 versus 16.1 minutes**. DNS and socket cases got slower, so improvement was not universal.

Three paired FCFS repeats used the same model/settings, a neutral warm-up before each measurement, and alternating index order. Candidate times were 8.9, 9.4, and 7.9 seconds; baseline times were 46.6, 11.2, and 21.4 seconds. Cached prompt processing remained evident even with neutral warm-up, and output lengths varied. These small repeats support the practical speed benefit but do not isolate a universal speedup or eliminate cache effects.

Two redundant Networking entries existed in the original index. Rebuilding with the original splitter reproduced all OS and text chunks exactly, but yielded 16 Networking chunks instead of 18. Those redundant entries affected baseline q02 and q17 contexts. Their removal is a comparison caveat; their effects must not be attributed solely to new boundaries.

## Validation and artifacts

28 backend tests and the frontend flow suite passed. After promotion, live retrieval returned the same IDs and distances as the reviewed trial for all 26 benchmark/scope cases. Stored text, source metadata, and vectors were checked against the candidate index. Source files, retrieval code, and answer prompt were verified unchanged.

- `chunking_trial_v2.json` / `.md`: complete answers, selected evidence, timings, fingerprints, and reviews.
- `chunking_trial_v2_manifest.json`: source hashes, policy hash, and chunk counts.
- `chunking_paired.json`: the six paired FCFS outputs and timings; warm-up requests excluded.
- `chunking_scope_check.json`: six additional scope/unsupported requests.
- `chunking_coverage_audit.json`: per-page source-word coverage result.
- `chunking_rollout.json` / `chunking_live_parity.json`: backup, promotion, and retrieval-parity evidence.
- `experiments/original_ingest_notes.py`: prior ingestion implementation.
- `experiments/chunking_v1.py`: rejected first prototype.

The original `baseline_full.json`, its reviews, and original committed source remain unchanged. Replay the original backed-up corpus explicitly:

```powershell
.\.venv\Scripts\python.exe experiments/chunking_trial.py --db chroma_db --collection test_notes_baseline_20261014 --output original_replay.json
```

Do not overwrite the frozen reports. The backup permits a return to the old index if later tests reveal a regression; restoring it after new uploads requires reviewing those new changes first.

Restart the backend to load the new ingestion code and refreshed index.
