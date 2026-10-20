# Retrieval and answer baseline

The active standalone retrieval and answer prompt now match the original committed implementation at `87b9c0365bbc9544e7d837c677fa17ef5a532925`. Its exact source is preserved in `benchmarks/original_rag.py`; the application does not import that reference file.

## Active path

1. Embed the user's question unchanged, once, using nomic-embed-text.
2. Search Chroma once for five matches. Add a course filter only when a course is selected; All courses has no filter.
3. Apply the original 1.1 distance cutoff to the best match. If it passes, send all returned chunks, unchanged, to the model.
4. Use the original short context-and-question prompt and stream one answer from llama3.2:3b.

Query rewriting, dual searches, individual-passage cutoffs, compaction, section selection, table recovery, variant filtering, multipart splitting, and the added system prompt are removed from the active path. The model's original default temperature is restored. Previous experimental code is archived under `experiments/`; older evaluation scripts explicitly import that archived policy.

Streaming, timing logs, chat persistence and management, and lazy document previews remain. Empty search results are handled safely. The Chroma path remains anchored to the repository. Saved-chat history is appended to the answer prompt to resolve references, without a rewriting model call; retrieval still uses the raw question. This history extension is tested separately from exact standalone parity.

The existing 8,192 context window and 180-second timeout are retained as runtime settings. They differ from the original constructor defaults and are recorded in every new live report. Matching retrieval and prompts does not imply identical stochastic answers or timings.

## Baseline evidence

`tests/test_retrieval.py` checks the restored standalone prompt, source list, and query arguments against the exact original implementation, using the same fixture results. It also checks All courses, the selected-course filter, the original cutoff, empty results, one-pass multipart answering, streaming timings, and saved history. Chat and frontend regression suites cover persistence and streaming behavior.

The user's exact regression, `What is SJF?` in a new chat, is recorded for All courses, Operating Systems, and Networking in `tests/baseline_cases.json`, alongside bus-topology scope controls and an unsupported question. Pre-reset raw search results are preserved in `sjf_scope_before_reset.json`. Actual reset answers, sources, selected full chunks, model settings, timing measurements, and fingerprints are in `retrieval_answer_baseline.json` and its Markdown companion. These focused cases do not establish general answer accuracy.

Run the focused benchmark without other Ollama work:

```powershell
.\.venv\Scripts\python.exe evaluate_answers.py --cases tests/baseline_cases.json --output baseline_trial.json
```

Run the broader 20-case set with a separate output:

```powershell
.\.venv\Scripts\python.exe evaluate_answers.py --output baseline_full_trial.json
```

## How a change earns its place

- Change one retrieval, prompt, or model setting at a time. Record exactly what changed.
- Run the same questions and corpus with all other settings held fixed; include All courses and selected-course pairs, follow-ups, multipart requests, and missing evidence.
- Review complete answers against the notes for correctness, completeness, and unsupported claims. Source presence or keyword matches alone are insufficient.
- Compare time to first text, total time, prompt processing time, and output token rate. Warm both runs consistently, avoid concurrent CPU/model work, and repeat timed runs before claiming a speed improvement.
- Keep a change only when the actual answers improve without a meaningful speed regression. Otherwise revert it. Preserve each report separately; resume only unchanged configurations.

The old `answer_baseline.json` measures the earlier modified pipeline, not the original implementation. Its results are historical and should not be presented as the original benchmark. The saved original source and the reset baseline are the comparison point going forward.

Restart the backend to load the reset.

## Recorded reset results

All six focused requests completed. All courses and Operating Systems both retrieved SJF and returned the correct acronym expansion, but omitted the scheduling definition, so both are rated partial. Networking correctly refused SJF. Bus topology was supported in both All courses and Networking. The unsupported question was refused. Four cases met all review criteria; two were incomplete. These are assistant reviews of development cases, not an independent accuracy estimate.

The pre-reset raw search also found the OS SJF passage for All courses; it did not establish the cause of the reported opposite-scope behavior. The exact earlier UI/backend result was not reproduced. Restart the backend and use new chats when comparing scopes.

19 backend tests and the frontend flow suite passed. Timing results are single runs with cold/warm differences; the 52.8-second All courses SJF run and 2.5-second Operating Systems run are not evidence that the course filter itself produced that speed difference. The full 20-case reset benchmark is now complete; see BASELINE_RESULTS.md and baseline_full.json for its separate results.

## Completed full baseline

All 20 requests completed; 14 met every assistant review criterion. Six were flagged for factual support or completeness. See BASELINE_RESULTS.md for the review categories and timing summary. Preserve baseline_full.json and its review files as the comparison point for future single-change trials.

## Ingestion update after the frozen baseline

Structural ingestion chunks are now active; see CHUNKING.md for trial results and limitations. Retrieval and answer prompts remain the original baseline. The original 47-entry corpus is preserved as collection test_notes_baseline_20261014. Replay it with the explicit collection argument documented in CHUNKING.md; do not treat the current live index as the original corpus.
