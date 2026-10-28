# Retrieval changes

The application keeps FastAPI, ChromaDB, nomic-embed-text, and llama3.2:3b.

- First questions search their original wording, without a rewrite model call.
- Questions with history search a guarded rewrite and the original question. The rewrite preserves explicit uppercase acronyms, identifiers, and numbers; a failed or invalid rewrite falls back to the original question. This is a safeguard, not a guarantee of semantic equivalence.
- Each search retrieves up to five candidates with the same course filter. The merged shortlist contains at most five passages, sorted by distance, filtered individually, and deduplicated by normalized text.
- Source labels are included in the answer prompt; duplicate file/page references are removed from the response. Sources indicate supplied evidence, not verified claim-level citations.
- The Chroma path is anchored to the repository, avoiding accidental empty databases when launched elsewhere.

## Evaluation

From the repository root:

```powershell
.\.venv\Scripts\python.exe evaluate_retrieval.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node tests/test_frontend.cjs
```

Ollama must be running with nomic-embed-text and llama3.2:3b for live evaluation. The evaluation reads the existing test_notes collection and generates rewritten questions, not answers. It writes retrieval_report.json. It includes 17 cases labelled using stored note passages: direct questions, paraphrases, comparisons, follow-ups, unsupported questions, a wrong-course question, and an empty-course question. File/page presence is a retrieval diagnostic; it does not prove the retrieved passage fully supports the answer. The text sample lacks page labels, so its cases are evaluated at file level.

The benchmark compares the legacy policy (rewrite every question, five results admitted by the best distance, cutoff 1.1) with the application policy. Rewrites use temperature 0 for repeatability; original-query embeddings are cached across modes, so the timings are diagnostic, not an unbiased speed comparison. Production uses the existing LlamaIndex Ollama configuration.

## Calibration and limits

The existing collection uses squared Euclidean distance (l2). Smaller means closer; these distances are not confidence percentages. A development-set sweep of cutoffs 0.8, 0.85, 0.9, 0.95, 1.0, 1.05, and 1.1 selected 1.0: it retained expected sources for all 13 answerable cases and rejected 3 of 4 unsupported cases. The old cutoff 1.1 rejected 2 of 4 unsupported cases. This is tuning on a small development set, not independent proof of improved general accuracy.

The remaining wrong-course case, bus topology within Operating Systems, retrieves unrelated OS pages below 1.0. The answer model must still check whether the context actually supports an answer. A distance threshold cannot establish factual support. Broader source-labelled tests and a held-out set should precede further tuning; hybrid retrieval or a reranker may help this failure.

Changing the embedding model, collection distance metric, or document corpus requires reevaluation. The benchmark rejects metrics other than l2 rather than silently applying this cutoff. Uploaded notes, chunk sizes, and embeddings were not changed or regenerated.
