"""Retrieval policy shared by the application and evaluation; no model imports."""
import logging
import math
import re
from time import perf_counter

logger = logging.getLogger(__name__)
DEFAULT_DISTANCE_LIMIT = 1.0  # Calibrated on the local 17-case development set (L2).

def history_text(history):
    return '\n'.join(f'{m.role}: {m.content}' for m in (history or [])[-4:])

def search_queries(question, history, complete):
    question = question.strip()
    if not history:
        return [question]
    prompt = f'''Rewrite the current question as one standalone question using the conversation only to resolve references.
Preserve technical terms, acronyms, identifiers, and numbers. Do not answer or add new facts.
Return only the question.
Conversation:
{history_text(history)}
Current question:
{question}'''
    try:
        rewritten = complete(prompt).text.strip().strip('"')
        # Reject obvious answers, empty output, and rewrites that drop explicit identifiers.
        identifiers = re.findall(r'\b[A-Z][A-Z0-9_]{1,}\b|\b\w+_\w+\b|\b\d+(?:\.\d+)?\b', question)
        if not rewritten or len(rewritten) > max(500, len(question) * 6) or any(term not in rewritten for term in identifiers):
            return [question]
        return [question] if rewritten.casefold() == question.casefold() else [rewritten, question]
    except Exception:
        logger.warning('Query rewrite failed; searching the original question', exc_info=True)
        return [question]

def query_collection(collection, embed, query, course, top_k=5):
    options = dict(query_embeddings=[embed(query)], n_results=top_k,
                   include=['documents', 'metadatas', 'distances'])
    if course:
        options['where'] = {'course': course}
    return collection.query(**options)

def passages_from_result(result):
    docs = (result.get('documents') or [[]])[0]
    metadata = (result.get('metadatas') or [[]])[0]
    distances = (result.get('distances') or [[]])[0]
    ids = (result.get('ids') or [[]])[0]
    return [dict(id=ids[i] if i < len(ids) else None, text=text, metadata=meta or {}, distance=float(distance))
            for i, (text, meta, distance) in enumerate(zip(docs, metadata, distances))
            if text and math.isfinite(float(distance))]

def retrieve(question, course, history, collection, embed, complete, distance_limit=DEFAULT_DISTANCE_LIMIT, legacy=False):
    started = perf_counter()
    if legacy:
        rewritten = complete(f'''Given the conversation history and the current question,
rewrite the current question as a standalone question.
Do not answer the question. Only return the rewritten question.
Conversation history:
{history_text(history)}
Current question:
{question}''').text.strip()
        queries = [rewritten]
    else:
        queries = search_queries(question, history, complete)
    candidates = []
    for query in queries:
        candidates.extend(passages_from_result(query_collection(collection, embed, query, course)))
    if legacy:
        selected = candidates if candidates and candidates[0]['distance'] <= distance_limit else []
    else:
        selected = []
        seen = set()
        for passage in sorted(candidates, key=lambda p: p['distance']):
            if passage['distance'] > distance_limit:
                continue
            key = ' '.join(passage['text'].split()).casefold()
            if key in seen:
                continue
            seen.add(key)
            selected.append(passage)
            if len(selected) == 5:
                break
    return dict(queries=queries, candidates=candidates, passages=selected,
                seconds=perf_counter() - started, distance_limit=distance_limit)


def compact_passages(question, passages):
    """Keep whole passages; discard near copies and use a smaller context budget."""
    budget = 3 if re.search(r"\b(compare|comparison|differences?|versus|vs|and)\b", question, re.I) else 2
    def shingles(text):
        words = re.findall(r"\w+", text.casefold())
        return set(tuple(words[i:i+5]) for i in range(max(0, len(words)-4)))
    kept = []
    fingerprints = []
    for passage in passages:
        passage = focus_passage(question, passage)
        fingerprint = shingles(passage['text'])
        # Only omit a passage if almost all of its ordered phrases are already present.
        if fingerprint and any(len(fingerprint & previous)/len(fingerprint) >= .9 for previous in fingerprints):
            continue
        kept.append(passage)
        fingerprints.append(fingerprint)
    stop = set("what is are a an the how why which when if its that it of to in on for with about explain compare comparison differences difference versus vs and happens can does do be".split())
    if budget == 3:
        stop.update({"topology", "topologies", "network", "networks", "algorithm", "algorithms", "scheduling"})
    topic_question = re.split(r"[.!?]\s*(?:keep|answer|respond|use|write)\b", question, maxsplit=1, flags=re.I)[0]
    terms = list(dict.fromkeys(word for word in re.findall(r"\w+", topic_question.casefold()) if word not in stop))
    chosen = []
    # Prefer passages that introduce a topic early, rather than mention it in passing.
    for term in terms:
        matches = []
        for index, passage in enumerate(kept):
            match = re.search(r"\b" + re.escape(term) + r"\b", passage['text'], re.I)
            if match:
                matches.append((match.start(), index))
        if matches:
            index = min(matches)[1]
            if index not in chosen:
                chosen.append(index)
    # Keep the distance-ranked fallback for terms absent from the retrieved text.
    if budget == 3 and len(chosen) >= 2:
        return [focus_passage(question, kept[index]) for index in chosen[:budget]]
    chosen.extend(index for index in range(len(kept)) if index not in chosen)
    return [focus_passage(question, kept[index]) for index in chosen[:budget]]


def focus_passage(question, passage):
    """Select complete matching headed/labelled sections across document formats."""
    text = passage['text']
    # Explicitly scoped variant explanations are optional context, not facts about
    # the default form. Keep them when a variant or its label is requested.
    wants_variants = bool(re.search(r'\b(variants?|versions?|forms?|preemptive)\b', question, re.I))
    scoped = r'[^.!?\n]*(?:\n[ \t]+[^.!?\n]*)*?\s*\(in the (?P<label>[^)\n]+?) variant\)\.?'
    def keep_variant(match):
        label_terms = set(re.findall(r'\w+', match.group('label').casefold()))
        requested = label_terms & set(re.findall(r'\w+', question.casefold()))
        return match.group(0) if wants_variants or requested else ''
    text = re.sub(scoped, keep_variant, text, flags=re.I)
    if not wants_variants:
        def keep_declaration(match):
            names = set(re.findall(r'\w+', match.group('names').casefold()))
            return match.group(0) if names & set(re.findall(r'\w+', question.casefold())) else ''
        text = re.sub(r'\([^()\n]*\bvariant\s*=\s*(?P<names>[^)\n]+)\)', keep_declaration, text, flags=re.I)
    passage = {**passage, 'text': text}
    terms = set(re.findall(r"\w+", question.casefold())) - set("the a an what is are and compare comparison differences difference system systems algorithm algorithms topology topologies network networks".split())
    patterns = [
        r"(?m)^(?:The|In the) (?P<label>[A-Z][\w-]*(?: [A-Z][\w-]*)*)\b",
        r"(?m)^[ \t]*(?:o|[\u2022\uf0b7])\s+(?P<label>[^:\n]{2,80}):",
        r"(?m)^(?P<label>(?:\d+\. )?[A-Z][A-Z0-9 ,()/?-]{3,})\r?\n[-=]{3,}",
    ]
    outlines = list(re.finditer(patterns[2], text))
    matches = outlines if outlines else [m for pattern in patterns[:2] for m in re.finditer(pattern,text)]
    aspects = {'pros','cons','advantages','disadvantages','type','how it works','best use case'}
    headings = sorted([m for m in matches if m.group('label').strip().casefold() not in aspects],key=lambda m:m.start())
    if not headings:
        return passage
    blocks = []
    prefix = text[:headings[0].start()]
    if any(re.search(r"\b"+re.escape(term)+r"\b",prefix[:150],re.I) for term in terms):
        blocks.append(prefix.strip())
    for i, heading in enumerate(headings):
        name = set(re.findall(r"\w+", heading.group('label').casefold()))
        end = headings[i+1].start() if i+1 < len(headings) else len(text)
        block = text[heading.start():end].strip()
        if name & terms and len(block[heading.end()-heading.start():].split()) >= 5:
            blocks.append(block)
    if not blocks:
        return passage
    return {**passage,'text':'\n\n'.join(blocks)}


def restore_table_context(passages, collection, course=None):
    """Recover adjacent indexed chunks when a table fragment has lost its context."""
    restored=[]
    for passage in passages:
        if not re.search(r"(?m)^\s*\|.*\|", passage['text']):
            restored.append(passage)
            continue
        match = re.search(r'-chunk-(\d+)$',passage.get('id') or '')
        file = passage['metadata'].get('file_name')
        if not match or not file:
            restored.append(passage)
            continue
        scope = course or passage['metadata'].get('course')
        where = {'$and':[{'file_name':file},{'course':scope}]} if scope else {'file_name':file}
        ids = collection.get(where=where,include=[])['ids']
        neighbours=[]
        index=int(match.group(1))
        for id in ids:
            number=re.search(r'-chunk-(\d+)$',id)
            if number and abs(int(number.group(1))-index)<=1:
                neighbours.append((int(number.group(1)),id))
        if len(neighbours)<2:
            restored.append(passage)
            continue
        data=collection.get(ids=[id for _,id in sorted(neighbours)],include=['documents','metadatas'])
        nodes={id:(text,meta) for id,text,meta in zip(data['ids'],data['documents'],data['metadatas'])}
        narrative=[id for _,id in sorted(neighbours) if not nodes[id][0].lstrip().startswith('|')]
        chosen=narrative or [id for _,id in sorted(neighbours)]
        for id in chosen:
            text,meta=nodes[id]
            restored.append({**passage,'id':id,'text':text,'metadata':meta})
    return restored
