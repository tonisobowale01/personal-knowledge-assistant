"""Original single-search retrieval baseline, with timing and safe empty results."""
from time import perf_counter
import re

DEFAULT_DISTANCE_LIMIT = 1.1


def history_text(history, question=None):
    recent = (history or [])[-4:]
    text = '\n'.join(f'{m.role}: {m.content}' for m in recent)
    if question is not None:
        query = retrieval_query(question, history)
        if query != question:
            anchor = query.removesuffix(f'\nFollow-up: {question}')
            if not any(m.role == 'user' and m.content.strip()[:600] == anchor for m in recent):
                text = f'user: {anchor}\n{text}'
    return text


def retrieval_query(question, history=None):
    """Supply a prior user topic for references, without generating a rewrite."""
    refers_back = re.compile(r'\b(?:it|its|they|them|their|this|that|these|those|former|latter)\b|^\s*(?:and\b|also\b|what about\b|how about\b)', re.I)
    if not history or not refers_back.search(question):
        return question
    # Walk back through dependent follow-ups to the latest explicit user topic.
    # Assistant answers are not used as factual search material.
    users = [m.content.strip() for m in history if m.role == 'user' and m.content.strip()]
    anchor = next((text for text in reversed(users) if not refers_back.search(text)), users[-1] if users else '')
    return f'{anchor[:600]}\nFollow-up: {question}' if anchor else question


def retrieve(question, course, collection, embed, history=None):
    started = perf_counter()
    query = retrieval_query(question, history)
    options = dict(query_embeddings=[embed(query)], n_results=5,
                   include=['documents', 'metadatas', 'distances'])
    if course:
        options['where'] = {'course': course}
    result = collection.query(**options)
    docs = (result.get('documents') or [[]])[0]
    metadata = (result.get('metadatas') or [[]])[0]
    distances = (result.get('distances') or [[]])[0]
    ids = (result.get('ids') or [[]])[0]
    candidates = [dict(id=ids[i] if i < len(ids) else None, text=text,
                       metadata=meta or {}, distance=float(distance))
                  for i, (text, meta, distance) in enumerate(zip(docs, metadata, distances))]
    # Original policy: gate on the best match, then supply all five full chunks.
    passages = candidates if candidates and candidates[0]['distance'] <= DEFAULT_DISTANCE_LIMIT else []
    return dict(queries=[query], history_used=query != question, candidates=candidates, passages=passages,
                seconds=perf_counter() - started, distance_limit=DEFAULT_DISTANCE_LIMIT)
