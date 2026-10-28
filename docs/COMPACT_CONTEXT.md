# Compact answer context

Retrieval still searches and filters the same candidates. Answer preparation removes passages whose ordered five-word phrases are at least 90% contained in an already retained passage. Remaining passages are selected using early mentions of question terms, with distance rank as fallback. Trailing answer-format instructions are excluded from topic selection. Simple questions use at most two whole passages; comparisons or questions containing and use at most three. This is a lightweight heuristic, not a trained reranker or hybrid search. It can miss evidence on questions outside the test set.

History is retained for query rewriting. When a distinct guarded standalone rewrite succeeds, the answer prompt uses that question instead of repeating prior long messages. If rewriting falls back to the original question, recent history stays in the answer prompt to preserve unresolved references. No AI summarization call, re-ingestion, or new model is added. Saved chats are unchanged.

An initial distance-only smaller budget lost required pages for bus definitions and comparisons; that version was not applied. Topic-aware selection retained expected sources for all 13 answerable cases in a replay of the saved 17-case benchmark. Overall checks remain 16/17: the pre-existing wrong-course bus question still falsely retrieves OS pages. Source presence is not proof of answer accuracy, and text samples are labelled at file level.

For the saved bus/star comparison, selected passage text fell from 6492 to 605 characters (about 91%). The retained bus passage states how devices share a cable and describes cable failure; the star passage states how devices connect through a hub/switch and describes hub failure. Clearly headed topology sections are extracted intact to avoid mixing star, mesh, and tree properties on the same page. Other passage formats are kept intact; no arbitrary character clipping is used. Comparisons with two identified topic passages do not add another passage solely to fill the budget.

compact_report.json records the replay. evaluate_retrieval.py now evaluates the compact selection used by the answer stage. Model prompt-processing speed has not been measured in a matched, repeated before/after experiment; shorter text is an observed result, not a guaranteed latency reduction.


Run evaluate_compact_context.py to repeat the saved-candidate evidence replay. A fresh retrieval run is still needed if indexed documents change.

Live checks exposed unsupported cost and reliability contrasts in the model output, including after compacting the evidence. The model still mixes prior knowledge into some answers. Source-labelled checks remain 16/17, but this does not establish answer correctness. The final section-focused live request processed the prompt in 6.04 seconds and began output after 6.19 seconds; generation took 40.96 seconds. This is a single warm request with possible prompt-cache effects and different input, not a controlled before/after speed benchmark. No claim of eliminating hallucinations is made.
