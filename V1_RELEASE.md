# Ash version 1: local-use release

Release pass completed October 19, 2026 in `C:\Users\tonis\Documents\ash`.

This milestone packages the existing local assistant for use. It does not certify every generated answer as correct or claim that the model's factual limitations have been solved.

## Included changes

- Fixed topic loss in long follow-ups. Search already anchored dependent questions to the latest explicit user topic, but the answer step only saw the last four messages. When that topic has fallen outside recent history, the answer's conversation context now includes the same bounded user-topic anchor (maximum 600 characters). The current question and original answer instructions stay intact. There is no additional model call, reranking or question-specific rule.
- Preserved five-chunk retrieval, the original standalone prompt, streaming, model settings, index and existing architecture. Short follow-ups whose topic is already in recent history retain their prior prompt contents.
- Added `Start-Ash.ps1` and `Stop-Ash.ps1`. Start checks installed models, reuses healthy services or starts them on localhost, writes logs and opens the app. Stop verifies process command lines before stopping Ash's listeners; it leaves unrelated processes, Ollama and saved data alone.
- Populated the previously empty `requirements.txt` with direct versions from the working environment and replaced the outdated README with setup, everyday-use, backup and limitation instructions.

## Acceptance checklist

| Check | Result and boundary |
|---|---|
| Long-chat topic retention | Regression reproduced before the fix; final test passes. Topic appears in conversation context, not as an extra question. |
| Standalone baseline behavior | Original prompt, sources and retrieval-call parity test passes. |
| Backend checks | 30 tests pass: chat persistence/isolation, rename/delete, streaming completion/error behavior, ingestion/chunking and preview serving. Generation is mocked in flow tests. |
| Frontend checks | Simulated DOM/request checks pass for chat creation/list refresh/reopen/continuation/reset, rename/delete/cancel/failures, UTF-8 streaming, source labels and preview links. |
| Running application | Backend and frontend stopped and started successfully through the new helpers; repeated startup reuses healthy services. |
| Live chat flow | Created temporary chats, generated and saved an exchange, continued from saved history, reopened four messages, renamed, checked isolation, deleted only those temporary chats, and verified the pre-existing chat list was unchanged. |
| Actual preview HTTP | PDF and text range requests returned the matching original bytes with inline disposition. No new ingestion was needed. |
| Limited browser check | Observed courses, original chat list and document controls; reopening the temporary saved chat displayed its messages and restored the course; New Chat cleared its display. Final page refreshed after cleanup. No complete manual browser interaction suite was run. |
| Installed dependencies | `pip check` reports no broken requirements. Direct pins match installed versions. |

The new machine setup instructions have not been tested in a clean environment. No cloud deployment, public-hosting setup or distribution installer was added.

## Live answer checks

The short smoke check exercised real Ollama generation and HTTP streaming. These are individual examples, not an accuracy percentage:

| Question | Manual result |
|---|---|
| What is SJF? | Partial: only expanded Shortest Job First; omitted the mechanism and non-preemptive behavior. This remains a model limitation. |
| Saved SJF chat: What are its advantages? | Supported minimum-average-waiting answer, with redundant commentary. No false no-starvation claim in this run. |
| Long Round Robin chat: quantum too large? | Final history-only version correctly answered that it degrades to FCFS. |
| Long star-topology chat: central device fails? | Final history-only version correctly answered that the whole network goes down. |
| Photosynthesis under Operating Systems | Correct refusal for the selected notes. |

The first implementation placed the resolved search query in the question slot. Its live Round Robin answer added a false starvation claim. That placement was removed; the final change only restores a missing topic in conversation context. The two affected long-history cases were rerun. Initial smoke results remain in `.run/v1_acceptance_first.json`, and final results and manual reviews are in `.run/v1_acceptance.json`. The reruns used warm/cached runtime state; their faster timings are not evidence of a speed improvement.

## Known limits and stopping point

The model can still invent or mix facts, give incomplete definitions, or miss a part of a combined question. Retrieved sources are supporting material to inspect, not verified citations for every generated claim. Ambiguous follow-ups can still require a topic name. CPU-only prompt processing remains slow on longer contexts.

The scope of this release is a usable local study assistant with persistent chats, streamed answers, course-filtered retrieval and document previews. Factual accuracy must still be checked against the notes. Further prompt, model, chunk-count, hybrid-search and reranking experiments are deferred; none is silently enabled here.

Start using the application at **http://127.0.0.1:3000**. See [README.md](README.md) for the single startup command and backups.
