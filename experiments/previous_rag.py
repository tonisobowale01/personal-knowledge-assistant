from pathlib import Path
import logging
import re
from time import perf_counter
from app.retrieval import retrieve, history_text, compact_passages, restore_table_context

import chromadb
import ollama
from llama_index.llms.ollama import Ollama


client = chromadb.PersistentClient(path=str(Path(__file__).resolve().parents[1] / "chroma_db"))

collection = client.get_or_create_collection(name="test_notes")

logger = logging.getLogger("uvicorn.error")

llm = Ollama(
        model="llama3.2:3b",
        base_url="http://127.0.0.1:11434",
        context_window=8192,
        temperature=0.0,
        system_prompt="You answer questions from supplied notes. Every factual clause must be directly supported by those notes. Do not supplement facts from memory. When notes only name a limitation, report that limitation without inventing how it occurs. Preserve negation and all qualifications. Use concise prose.",
        request_timeout=180.0
    )

def prepare_evidence(question, course=None, history=None):
    recent_history = history_text(history)
    result = retrieve(
        question, course, history, collection,
        lambda query: ollama.embed(model="nomic-embed-text", input=query)["embeddings"][0],
        llm.complete,
    )
    logger.info("Retrieval: %.3fs, %d queries, %d selected passages", result["seconds"], len(result["queries"]), len(result["passages"]))
    resolved_question = result["queries"][0]
    passages = compact_passages(resolved_question, restore_table_context(result["passages"], collection, course))
    # Successful standalone rewrites replace history in the answer stage.
    # If rewriting fell back, retain context needed to interpret references.
    if len(result["queries"]) > 1 or not history:
        recent_history = ""
    logger.info("Answer context: %d of %d passages, %d characters", len(passages), len(result["passages"]), sum(len(p["text"]) for p in passages))
    if not passages:
        return None, [], result["seconds"], [], resolved_question
    sources = []
    seen_sources = set()
    for passage in passages:
        metadata = passage["metadata"]
        source = (metadata.get("file_name"), metadata.get("page_label"))
        if source not in seen_sources:
            sources.append({"file": source[0], "page": source[1]})
            seen_sources.add(source)
    context = "\n\n".join(
        f"[Source: {p['metadata'].get('file_name', 'unknown')}, page {p['metadata'].get('page_label', 'unknown')}]\n{p['text']}"
        for p in passages
    )

    prompt = f"""Answer the question concisely using only the notes below.
Address every requested part with one short paragraph per topic. Do not repeat facts in a concluding summary.
Before stating a fact, check its exact subject, negation, condition, and consequence against the notes.
Keep distinctions between individual components and the whole system explicit.
Preserve qualifiers about variants and exceptions: a variant-specific behavior is not a property of every form of the topic.
Do not transfer a property between neighbouring definitions or change a stated condition or consequence.
Do not add concluding comparisons, benefits, or consequences unless the notes support them.
When notes state a limitation without explaining its mechanism, report the limitation without inventing a mechanism.
Use at most two sentences per topic unless the question explicitly requests more detail.
Do not invent quotations. If evidence is missing or ambiguous, state that explicitly.
Conversation is only for resolving references, never factual evidence.
Conversation: {recent_history}
Notes:
{context}
Question: {resolved_question}
Answer:"""


    return prompt, sources, result["seconds"], passages, resolved_question

def prepare_question(question, course=None, history=None):
    prompt, sources, seconds, _, _ = prepare_evidence(question, course, history)
    return prompt, sources, seconds


def definition_topics(question):
    match = re.match(r"^\s*(?:what (?:is|are)|define|explain|describe)\s+(.+?)[?!.]*$", question, re.I)
    if not match:
        return []
    topics = [part.strip() for part in re.split(r",\s*(?:and\s+)?|\s+and\s+", match.group(1), flags=re.I) if part.strip()]
    if any(re.search(r"\b(it|this|that|these|those|its)\b", topic, re.I) for topic in topics):
        return []  # Keep history-based references in the ordinary rewrite flow.
    return topics if 2 <= len(topics) <= 6 else []


def stream_question(question, course=None, history=None):
    topics = definition_topics(question)
    if topics:
        started = perf_counter()
        answer_parts = []
        sources = []
        seen_sources = set()
        retrieval_seconds = generation_seconds = 0.0
        first_text = None
        for topic in topics:
            labelled = False
            for event in stream_question(f"What is {topic}?", course=course, history=None):
                if event["type"] == "delta":
                    if not labelled:
                        heading = ("\n\n" if answer_parts else "") + topic + ":\n"
                        answer_parts.append(heading)
                        yield {"type": "delta", "text": heading}
                        labelled = True
                    if first_text is None:
                        first_text = perf_counter() - started
                    answer_parts.append(event["text"])
                    yield event
                elif event["type"] == "done":
                    for source in event["sources"]:
                        key = (source.get("file"), source.get("page"))
                        if key not in seen_sources:
                            seen_sources.add(key)
                            sources.append(source)
                    retrieval_seconds += event.get("timings", {}).get("retrieval_seconds", 0)
                    generation_seconds += event.get("timings", {}).get("generation_seconds", 0)
                else:
                    yield event
        yield {"type": "done", "answer": "".join(answer_parts), "sources": sources,
               "timings": {"retrieval_seconds": retrieval_seconds, "generation_seconds": generation_seconds,
                           "first_text_seconds": first_text, "parts": len(topics)}}
        return
    yield {"type": "status", "message": "Finding relevant notes..."}
    prompt, sources, retrieval_seconds, evidence, resolved_question = prepare_evidence(question, course, history)
    if prompt is None:
        answer = "I could not find that in the notes."
        yield {"type": "delta", "text": answer}
        yield {"type": "done", "answer": answer, "sources": [], "timings": {"retrieval_seconds": retrieval_seconds}}
        return
    yield {"type": "status", "message": "Reading notes and preparing the answer..."}
    started = perf_counter()
    first_text = None
    parts = []
    final = None
    stream = llm.stream_complete(prompt)
    try:
        for chunk in stream:
            raw = chunk.raw or {}
            if chunk.delta:
                if first_text is None:
                    first_text = perf_counter() - started
                parts.append(chunk.delta)
                yield {"type": "delta", "text": chunk.delta}
            if raw.get("done"):
                final = raw
    finally:
        if hasattr(stream, "close"):
            stream.close()
    if final is None or not parts or final.get("done_reason") == "length":
        raise RuntimeError("The model response did not finish normally")
    generation_seconds = perf_counter() - started
    eval_seconds = (final.get("eval_duration") or 0) / 1e9
    timings = {"retrieval_seconds": retrieval_seconds, "generation_seconds": generation_seconds,
               "first_text_seconds": first_text, "load_seconds": (final.get("load_duration") or 0) / 1e9,
               "prompt_eval_seconds": (final.get("prompt_eval_duration") or 0) / 1e9,
               "output_tokens_per_second": (final.get("eval_count") or 0) / eval_seconds if eval_seconds else None}
    logger.info("Answer timings: %s", timings)
    yield {"type": "done", "answer": "".join(parts), "sources": sources, "timings": timings}


def ask_question(question, course=None, history=None):
    for event in stream_question(question, course, history):
        if event["type"] == "done":
            return {"answer": event["answer"], "sources": event["sources"]}
    raise RuntimeError("Missing final answer")


def get_courses():
    data = collection.get(include=["metadatas"])

    courses = set()

    for metadata in data["metadatas"]:
        course = metadata.get("course")

        if course:
            courses.add(course)

    return sorted(courses)

def get_documents():
    data = collection.get(include=["metadatas"])

    files = {}

    for metadata in data["metadatas"]:
        file_name = metadata.get("file_name")
        course = metadata.get("course")

        if file_name:
            files[file_name] = course

    return [
        {
            "file": file_name,
            "course": course
        }
        for file_name, course in sorted(files.items())
    ]

def delete_document(file_name):
    collection.delete(where={"file_name": file_name})
