# Answer grounding correction

The experimental quote-only validator was removed after it failed a real multi-topic question. It could discard relevant definitions because PDF headings and line wrapping prevented exact whole-statement matches, then display an irrelevant but exact quote. Exact quotation did not establish relevance or completeness.

The app again streams explanatory prose using the compact retrieved evidence. The prompt requires all requested topics to be answered separately, in the requested order, with missing evidence stated explicitly. Related concepts must not replace the requested definition. This applies to all questions without a question-specific switch. Explicit lists of two to six definition topics are processed separately and assembled into one answer. This can require multiple model calls, but it streams each part as it becomes available and saves only one complete exchange. Topics containing unresolved pronouns stay in the history-aware ordinary path. No model download is added.

A regression check confirms multi-part evidence is preserved and ordinary prose passes through the streaming pipeline. The reported virtualization/clustering/multicore case has the relevant definitions in pages 21, 13, and 11 of Introduction to Operating Systems.pdf. Saved chats, document previews, context size, and compact retrieval are unchanged.

These instructions improve expected behavior but are not a formal semantic validator. The model can still make unsupported claims; no claim that hallucinations have been eliminated is made.
