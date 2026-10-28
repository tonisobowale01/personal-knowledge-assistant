# October 26 issue follow-up

The resolved timeout paragraph in the user's issue file was excluded. Changes follow the requested order: source display, upload feedback, then a small regression set for follow-ups and factual accuracy.

## Implemented

- Each new answer has a native, closed **Show sources** disclosure containing deduplicated preview links and search scope. The long duplicate source paragraph is removed. Sources stay associated with their answer during the current page session. Historical sources are still not stored with reopened chats.
- Upload feedback distinguishes file transfer (with a transfer percentage when available) from server processing. Upload/file/course controls stay disabled until completion or failure, and repeated clicks cannot submit duplicate requests. Completion is shown only after the server finishes ingestion. Browser navigation is guarded during an upload; standard browser restrictions still apply.
- A failed connection says processing could not be confirmed, rather than pretending the backend stopped. A successful upload followed by a list-refresh failure is reported separately, to discourage duplicate uploads.
- PDF parsing and embedding work now run in a worker thread so the async upload route does not block the API's event loop. This does not add background jobs or falsely acknowledge ingestion before it finishes.
- The existing topic heuristic now covers person pronouns (`he`, `him`, `his`, `she`, `her`, `hers`) in addition to the existing references. It still uses prior user topics, one embedding and one search, with the same model, prompt, five passages and cutoff. No composer-, subject- or question-specific production rule was added.

## Validation

- 32 backend tests pass, including the new person-reference regression and an upload check that verifies processing runs outside the event loop and finishes before success is returned.
- Frontend checks pass for collapsed, deduplicated source links; transfer/processing/completion feedback; disabled controls and duplicate prevention; connection-failure recovery; and the prior chat/stream/preview flows. Upload states were exercised with a controlled XMLHttpRequest mock, not a new permanent document upload.
- In the running browser, a temporary answer displayed **Show sources (5)** collapsed by default; expanding it showed search scope and five page-specific preview links. The temporary chat was removed afterward, preserving pre-existing chats. The updated app is running on localhost.
- `tests/issue_cases.json` records 11 small development cases from the screenshots. `experiments/check_reported_issues.py` captures before/after retrieval traces and three real answers. Private full evidence/answers are in `.run/reported_issues.json`, excluded from Git.
- Before the pronoun change, `what is unique about him` returned no usable passages. Afterward it retains Wagner as the user topic and retrieves his notes. This demonstrates search recovery, not a guarantee that every generated answer will be correct.
- Live Wagner-beliefs follow-up: supported answer about his roles, influence and belief that opera could revolutionize society.
- Live `So who is her father` after the Valkyries question: correctly answers Wotan, supported by the retrieved farewell/daughter passage.
- Live natural-language deadlock question: still refuses because its retrieved context does not contain the full four-condition list. It is not marked fixed.

## Remaining accuracy work

The initial check found different evidence sets for the three deadlock phrasings. The subsequent heading-selection trial recovered the full conditions page for all three, and all three live answers named the four conditions correctly. That general selection change was applied after regression checks; see `RETRIEVAL_HEADING_CHECK.md`. It does not solve every wording or answer-quality problem.

The bel canto examples also demonstrate a different failure: the right notes can be retrieved while the model confuses an influence with a creator. The pronoun fix does not guarantee correct relationship reasoning. Neither this nor the previous rejected prompt trial justifies claiming factual accuracy is solved.

The disappearing-reply investigation reproduced the reload cause in VS Code Live Preview: a chat-database write automatically reloaded the page and erased an unsent question. This also explains why chat creation can interrupt streaming. The page now uses Live Preview's supported `data-server-no-reload` body attribute. Repeating the database-write test preserved the question. Explicit browser refresh still works; source changes require manual refresh. The upload guard does not make browser/server interruptions resumable.

Repeated-question speed is not training or learning. Existing conversation context and runtime caching can affect latency. This pass makes no benchmarked speed-improvement claim.
