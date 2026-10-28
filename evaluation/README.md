# Evaluating Ash

This folder is the public-facing entry point for evaluation evidence. The results below are historical development measurements, not a claim of general accuracy or a new benchmark of the current frontend release.

## Completed baseline: October 14, 2026

The same 20 reference-note questions exercised definitions, paraphrases, comparisons, multipart requests, follow-ups, unsupported questions, a wrong course, and an empty course. All 20 requests completed. Each answer was reviewed by the assistant against the supplied reference notes for completeness, supported claims, and handling of missing evidence. This was not independent human grading or a held-out test set.

| Measurement | Historical result |
| --- | ---: |
| Answers meeting all content-review criteria | 14 of 20 |
| Median retrieval, all 20 cases | 0.11 s |
| Median first text, 17 answerable cases | 35.5 s |
| Median completion, 17 answerable cases | 43.2 s |
| Median model output rate | 6.2 tokens/s |
| Complete run wall time | About 16.1 minutes |

The local `baseline_full.json` review and timing summaries match these figures. End-of-run checks recorded unchanged code, fixture, corpus, model settings, and model digests. The run used `llama3.2:3b`, an 8,192-token context, a 180-second timeout, default temperature, and no fixed seed. Its environment record reports Python 3.14.6 and Ollama 0.40.3 on Windows. These historical versions differ from later acceptance environments.

Prompt processing accounted for about 78% of measured model-generation time, which already includes prompt processing. Cold/warm state and caching were uncontrolled. One run does not establish a causal speed improvement, and the 14/20 result must not be presented as a current 70% general-accuracy claim.

Read the [completed baseline](BASELINE_RESULTS.md) for failure categories and the frozen comparison point.

## Later focused checks are separate

The [October 26 heading-selection check](RETRIEVAL_HEADING_CHECK.md) compared evidence sets for 33 case/history/course combinations. It retained the reference pages found previously and recovered the complete four-condition passage for three deadlock phrasings. Three targeted local-model answers named all four conditions.

That is evidence coverage plus three targeted answers, not a new 33-question answer-accuracy score. No full new answer benchmark or controlled timing study was run. The theatre question already retrieved relevant material but still exposed a synthesis/relationship weakness. Correct retrieval and correct answers need separate evaluation.

Later [release checks](../docs/V1_RELEASE.md) cover software behavior, previews, persistence, and a few live answers. Passing them does not validate every generated answer. Chunking and prompt trials are historical experiments, not automatically comparable additions to the baseline score.

## Evidence inventory

Original reports and scripts are preserved in place so historical paths and fingerprints continue to work:

| Location, relative to repository root | Evidence |
| --- | --- |
| `baseline_full.json` | Actual answers, selected context, reference text, settings, fingerprints, judgments, and timings |
| `baseline_full.md`, `baseline_full_reviews.json` | Readable per-case review and explicit judgments |
| `baseline_environment.json` | Recorded package/model versions and model fingerprints |
| `tests/baseline_cases.json`, `tests/answer_cases.json` | Development fixtures and expected points; confirm the fixture hash for the run being reproduced |
| `benchmarks/original_rag.py`, `benchmarks/original_revision.json` | Frozen original implementation and source revision |
| `benchmarks/retrieval_before_heading_trial.py` | Retriever before the later heading-selection change |
| `.run/heading_trial.json`, `.run/remaining_evidence.json` | Private focused retrieval evidence |
| `.run/v1_final_check.json` | Private final local acceptance record |
| `experiments/`, root `evaluate_*.py` and `benchmark_*.py` | Reproduction and historical trial tools |

Local raw reports are intentionally ignored; they will not be present in a fresh clone. Some scripts expect the original course documents and index. The example questions and reference metadata may also be specific to the author's corpus. Do not promise out-of-the-box reproduction without supplying an appropriate permitted corpus.

## Run a new evaluation deliberately

From the repository root, with Ollama active and the intended notes indexed:

```powershell
New-Item -ItemType Directory -Force evaluation/private | Out-Null
.\.venv\Scripts\python.exe evaluate_answers.py --cases tests/baseline_cases.json --output evaluation/private/answers-new.json
```

Use a new output name for every changed configuration. The current runner calls the current pipeline: running it today does not recreate the old implementation automatically. Do not overwrite the frozen reports. Check [baseline instructions](../docs/BASELINE_RESET.md) and [answer-review instructions](../docs/ANSWER_BENCHMARK.md) before repeating a historical run; some described pipeline stages are historical.

Review complete answers against the notes, including omissions and unsupported additions. Record the code revision, corpus/fixture hashes, model versions/settings, hardware, failures, and review method. For speed comparisons, repeat matched runs with consistent warm-up and caching conditions. Keep retrieval, first-text latency, total latency, and decode throughput separate. No new expensive model evaluation was started by the cleanup.

## What to share

Keep this summary and reference implementations in Git. Review fixtures and summaries for document-specific details before publishing. Do not commit raw traces, reference-text snapshots, uploaded PDFs, personal questions, model outputs copied from private notes, or absolute local paths without reviewing and redacting them. `evaluation/private/` is ignored for new raw outputs.

A defensible project explanation is: “Evaluated a local RAG assistant on 20 development questions, reviewing source support and answer completeness while measuring retrieval and generation latency; identified synthesis errors despite relevant retrieval and CPU prompt-processing bottlenecks.” Add numerical findings only with their historical scope and review limits.
