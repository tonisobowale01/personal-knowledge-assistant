"""One semantic search, then heading-aware selection of five full passages."""
from time import perf_counter
import re

DEFAULT_DISTANCE_LIMIT = 1.1
CANDIDATE_LIMIT = 20
PASSAGE_LIMIT = 5
HEADING_STOP_WORDS = set('a an the what which who whom whose is are was were be been being do does did can could would should will may might to of for in on at by from with and or if then than that this these those how when where why it its he his she her they their we our you your'.split())


def heading_terms(text):
    words = re.findall(r'[^\W\d_]+', text.casefold())
    return {word[:-1] if len(word) > 4 and word.endswith('s') and not word.endswith('ss') else word
            for word in words if word not in HEADING_STOP_WORDS}


def heading_score(text, query):
    # Conservative, bounded heading hint; no topic-specific words or answer rules.
    lines = [line for line in text.splitlines() if re.search(r'[^\W\d_]', line)]
    return len(heading_terms('\n'.join(lines[:2])) & heading_terms(query))


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
    refers_back = re.compile(r'\b(?:it|its|he|him|his|she|her|hers|they|them|their|this|that|these|those|former|latter)\b|^\s*(?:and\b|also\b|what about\b|how about\b)', re.I)
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
    options = dict(query_embeddings=[embed(query)], n_results=CANDIDATE_LIMIT,
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
    # Preserve the original best-semantic-match gate. Only selection/order changes.
    passages = sorted(candidates, key=lambda p: (-heading_score(p['text'], query), p['distance']))[:PASSAGE_LIMIT] \
        if candidates and candidates[0]['distance'] <= DEFAULT_DISTANCE_LIMIT else []
    return dict(queries=[query], history_used=query != question, candidates=candidates, passages=passages,
                seconds=perf_counter() - started, distance_limit=DEFAULT_DISTANCE_LIMIT)
