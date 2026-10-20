> Historical experiment results below. The active baseline and current workflow are documented in BASELINE_RESET.md.

# Answer-quality baseline

Twenty questions cover definitions, paraphrases, failure conditions, comparisons, a multi-part question, follow-ups, unsupported questions, wrong-course retrieval, and an empty course. Expected points come from the indexed Networking notes, Introduction to Operating Systems slides, and os_sample.txt. These are reference-note expectations, not a claim that all statements in the notes are universally correct.

Run from the project root while avoiding other requests to Ollama:

```powershell
.\.venv\Scripts\python.exe evaluate_answers.py
```

The benchmark uses the actual stream_question pipeline, including retrieval, rewriting, compact evidence, and multi-part handling. It does not save chats, alter documents, or change model settings. Each completed question is written to answer_baseline.json and an answer_baseline.md review sheet. Partial answers and errors are retained as failures to complete, rather than discarded. The first-text measurement includes headings and the current streaming behavior. Cold loading, caches, background work, and CPU temperature affect timings; they are not an unbiased speed comparison.

Resume an interrupted run:

```powershell
.\.venv\Scripts\python.exe evaluate_answers.py --resume
```

Run selected cases into a separate report:

```powershell
.\.venv\Scripts\python.exe evaluate_answers.py --ids q05 q12 q18 --output answer_trial.json
```

Review completeness, support for claims, and handling of missing evidence against the expected points and source pages. Ratings start as null. Keyword matches and source-list presence are not used as automatic correctness scores. A model-generated judge is not added to ordinary requests. Manual reviews should mark pass, partial, fail, or not-applicable with a brief rationale. This 20-case development set is not a held-out general-accuracy estimate.

The runner records model settings and hashes of retrieval/answer code. Fresh runs also snapshot and hash indexed reference passages; the initial run began before that snapshot feature was added, so its evidence can be attached afterwards from the same verified collection. Resume only with unchanged code, model, corpus, and fixture; otherwise use a new output file to avoid mixing different configurations.


## Initial baseline

All 20 requests completed. Assistant review against the reference notes marked 12 as meeting the three content-review criteria and flagged 8: q03, q05, q08, q10, q11, q15, q16, and q17. These are review judgments on a small development set, not an independently measured general accuracy rate. Highlights include the wrong central-hub-failure conclusion, SJF/FCFS confusion, a starvation claim contradicting the notes, and an incomplete OS definition. The three-topic question covered all requested definitions. The wrong-course refusal succeeded but still listed unrelated source pages, a separate source-display issue.

The initial run used the app's existing settings, and those settings were not changed. Reference snapshots and the corpus fingerprint were attached after completion. Claims were reviewed against reference notes; the initial run did not capture each actual selected excerpt. Fresh runs capture those excerpts too, helping distinguish retrieval/context omissions from generation errors.

Manual review data is in answer_reviews.json. After reviewing a fresh run, attach review notes with review_answer_baseline.py (use --report and --reviews to select other files). Avoid applying old reviews to changed outputs. The readable report is answer_baseline.md; complete answers, timings, references, code fingerprints, and ratings are in answer_baseline.json.
