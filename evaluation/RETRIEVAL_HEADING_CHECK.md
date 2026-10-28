# Focused deadlock and theatre check — October 26

## Findings

The exact failed theatre question and preceding saved user history were inspected read-only. The first passage already contained the slide naming King Ludwig II as Wagner's patron, followed by a separate bullet about a special theatre in Bayreuth. This is an answer-grounding/relationship issue rather than a missing-file problem. The notes do not explicitly identify the person who physically built the theatre; the model should not silently equate patron and builder. The existing reference heuristic also attached an earlier Valkyries topic because the question contains `that`; that limitation was not changed in this experiment.

For `what are the conditions for deadlocks to happen`, the complete four-condition passage in the deadlock lecture was ninth in semantic order. Only five passages were being sent, so the answer model lacked the full list. The natural and four-condition phrasings retrieved mostly handling/prevention; the keyword phrasing included the relevant list.

A query-prefix-only trial did not solve these cases and weakened the previously successful keyword query's evidence set, so it was not applied. The [embedding model's documentation](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5) describes paired query/document task prefixes; this experiment did not rebuild the document embeddings or establish a complete prefixed-index comparison.

## One applied change

Search still makes one embedding call and one Chroma query, with the same course filter and original best-semantic-distance gate. It requests up to 20 candidates, then chooses five using generic overlap between query terms and the first two text-bearing lines of each passage, with semantic distance breaking ties. The full selected text is passed through unchanged.

No question-specific replacement, named-composer rule, deadlock keyword override, extra LLM call, new lexical index, prompt rewrite, model change, reingestion or saved-chat edit is involved. The previous retriever is preserved in `benchmarks/retrieval_before_heading_trial.py`.

## Evidence and limits

- 33 distinct case/history/course combinations were compared, including the previous 20-case fixture set, the user's screenshot cases and the two new theatre questions. Evidence sets and full passage text are stored privately in `.run/heading_trial.json`; the initial inspection is in `.run/remaining_evidence.json`.
- Every reference file/page present in the baseline results for the existing reference fixtures remained present in the trial results. This is an evidence-coverage check, not an answer-accuracy score.
- The full four-condition page now appears in all three deadlock contexts. Three actual local-model answers named mutual exclusion, hold and wait, no preemption and circular wait correctly. The natural and keyword versions explained the conditions; the four-condition version returned their names only.
- The theatre and King Ludwig evidence lists were unchanged by this trial. The theatre answer problem is not marked fixed; a stochastic answer changing with identical passages would not establish a retrieval improvement.
- Heading hints are approximate: first text lines can include boilerplate, prose or broad chapter headings. Poorly formatted notes and ambiguous questions may still select weak passages. Keeping reference pages does not prove every answer remains correct.
- The model and prompt still vary in output. One answer per target phrasing is a small development check, not independent human evaluation or statistical proof. A full new answer-quality benchmark was not run.
- These are not controlled CPU speed measurements. Retrieval remained small compared with generation in the focused runs, but one generation was unusually slow. Request count and prompt passage count are unchanged; neither overall speed preservation nor a speedup is claimed.

As of the October 27 version-one freeze, further tuning is deferred. The theatre case is recorded for a future, separate grounding investigation only if real study use makes it a repeated disruptive problem. Do not add a canned Ludwig answer or make a broad prompt change on the strength of these retrieval results.
