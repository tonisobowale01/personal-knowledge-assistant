# Follow-up retrieval regression

The baseline reset removed history from search while retaining it in the answer prompt. Consequently `What are its advantages` searched for generic advantages, not SJF. The screenshot's All courses search was reproduced: it selected OS pages 6, 14 and 3 plus Networking pages 5 and 6, none of which supplied the requested SJF advantage.

## Focused fix

Dependent questions containing references such as `its`, `that`, or `their`, or beginning with `And`/`What about`, now include the latest explicit user question in the embedding input. The SJF example searches:

```text
What is SJF
Follow-up: What are its advantages
```

The original current question remains in the answer prompt, with recent conversation available to interpret it. Assistant answers are not used as factual search material. Dependent chains walk back to an explicit user topic; a new standalone topic replaces the old topic. Attached user context is bounded to 600 characters.

This is a lightweight reference heuristic, not a general semantic resolver. Ambiguous references across several topics remain a limitation. It adds no model-rewriting call: one embedding, one Chroma search, the same five full passages and cutoff, and one streamed generation remain. Standalone questions preserve original query and prompt behavior.

## Validation and limits

- 29 backend tests and frontend flow checks passed, including topic switches, dependent chains, saved history, and original standalone parity.
- Five live cases are saved in `followup_check.json`: SJF advantages under All courses and OS, Round Robin quantum, central-star-device failure, and a switch from SJF to Round Robin advantages.
- Both SJF cases now retrieve the SJF notes and identify the minimum-average-waiting advantage. However, their generated answers add false fairness/equal-priority claims. Search recovery is verified; those SJF answers do not pass factual review.
- The Round Robin quantum, star failure, and Round Robin topic-switch answers are supported by their notes.
- Source labels are deduplicated in the browser, and text files no longer show `page null`. API source metadata and retrieval ranking are unchanged by this display cleanup.

The model, prompt, chunking policy and index are unchanged. The frozen baseline reports remain available; follow-up retrieval is a deliberate change from that baseline. Restart the backend and refresh the frontend before retesting.
