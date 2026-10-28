# Completed retrieval and answer baseline

Run date: October 14, 2026. All 20 cases completed and were reviewed against the supplied reference notes. The full run took about 16.1 minutes. Application code, question fixtures, indexed corpus, model settings, and model fingerprints were verified unchanged at the end.

## Answer quality

14 of 20 answers met every review criterion. This is an assistant review of a small development set, not an independently measured general accuracy rate.

| Finding | Cases | Evidence |
|---|---|---|
| Factual errors | q05, q15 | Bus/star comparison transfers tree properties and adds unsupported redundancy. SJF names starvation but invents a head-of-queue mechanism. |
| Incomplete answers | q08, q10 | OS answer omits hardware/resource management; clustering answer omits monitoring and takeover despite receiving those notes. |
| Unsupported extrapolations | q12, q13 | Multipart answer adds blanket multicore performance improvement; clustering comparison infers asymmetric clustering is less complex. Core definitions otherwise meet expectations. |

Both follow-up cases were supported. Unsupported, wrong-course, and empty-course requests were correctly refused. The multipart answer covered all three requested topics in one model pass, with the extra performance claim flagged above.

The refusals in q18 and q19 still return unrelated retrieved pages as sources. That is recorded separately as a source-display issue, rather than treated as an invented factual answer.

## Speed

| Measurement | Observed result |
|---|---:|
| Median retrieval time, all 20 requests | 0.11 seconds |
| Median time to first text, 17 answerable cases | 35.5 seconds |
| Median total time, 17 answerable cases | 43.2 seconds |
| Median time to first text, all 20 cases | 28.1 seconds |
| Median total time, all 20 cases | 42.2 seconds |
| Median output token rate, requests using the model | 6.2 tokens/second |
| Slowest request, q05 comparison | 139.0 seconds |

Ollama reported 744.8 seconds of prompt processing out of 960.1 seconds of measured model-generation time, about 78%. That generation measurement includes loading, prompt processing, and producing text; prompt time is already included, not added on top. In q07, a one-sentence socket answer took 93.7 seconds, including 90.9 seconds reading the prompt.

These are single-run timings with uncontrolled cold/warm and cache effects. They describe this run; they do not establish a speed improvement or prove a course filter changes latency. Repeated matched timing runs are required when evaluating a proposed improvement.

## Frozen comparison point

- `baseline_full.json`: all actual answers, complete selected context, reference notes, timings, settings, fingerprints, and verification results.
- `baseline_full.md`: per-question expected points, actual answers, and fresh review notes.
- `baseline_full_reviews.json`: the 20 explicit review judgments.
- `baseline_environment.json`: software versions and model fingerprints.
- `benchmarks/original_rag.py`: exact original committed implementation, with its revision recorded alongside it.
- `retrieval_answer_baseline.json`: the earlier six-case scope check, including the user's exact SJF question under All courses, Operating Systems, and Networking. It is a separate run, not additional questions in the 20-case score.

The active standalone retrieval policy and prompt match the original source. Streaming, timings, anchored database paths, safe empty results, saved-chat history in the prompt, the existing 8,192 context window, and the 180-second timeout remain as documented in `BASELINE_RESET.md`. The model uses its original default temperature; no explicit seed is fixed.

## What the next experiment must beat

Keep these reports unchanged. Change one thing, use a new output file, and run the same questions with the same corpus, models, and runtime settings. Review whole answers against the notes, including omissions and extra claims, before comparing speed. Repeat timing trials with matching warm-up and cache conditions before accepting a speed claim.

This run supports testing cleaner document chunks next: the bus/star error mixes adjacent concepts, while prompt processing dominates latency. It does not prove that a chunking change will solve the model's omissions or invented explanations. That remains an experiment.
