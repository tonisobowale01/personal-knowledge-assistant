from pathlib import Path
import logging
from time import perf_counter
from app.retrieval import retrieve, history_text

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
        request_timeout=180.0
    )

def prepare_evidence(question, course=None, history=None):
    result = retrieve(
        question, course, collection,
        lambda query: ollama.embed(model="nomic-embed-text", input=query)["embeddings"][0],
        history=history,
    )
    passages = result["passages"]
    logger.info("Retrieval: %.3fs, 1 query, %d selected passages, history context: %s", result["seconds"], len(passages), result["history_used"])
    if not passages:
        return None, [], result["seconds"], [], question
    sources = [{"file": p["metadata"].get("file_name"), "page": p["metadata"].get("page_label")}
               for p in passages]
    context = "\n\n".join(p["text"] for p in passages)
    # Exact original answer prompt for standalone questions.
    prompt = f"""
    Answer the question using only the context below.

    If the answer is not in the context, say:
    "I could not find that in the notes."

    Context:
    {context}

    Question:
    {question}
    """
    # Keep saved-chat references usable without adding a query-rewriting pass.
    if history:
        prompt += "\nConversation (only for understanding references in the question):\n" + history_text(history, question)
    logger.info("Answer context: %d full passages, %d characters", len(passages), len(context))
    return prompt, sources, result["seconds"], passages, question

def prepare_question(question, course=None, history=None):
    prompt, sources, seconds, _, _ = prepare_evidence(question, course, history)
    return prompt, sources, seconds


def stream_question(question, course=None, history=None):
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
