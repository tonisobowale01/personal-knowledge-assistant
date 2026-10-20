from pathlib import Path
import chromadb
import ollama
from llama_index.core import SimpleDirectoryReader
from llama_index.readers.file import PDFReader
from app.chunking import chunk_document

client = chromadb.PersistentClient(path=str(Path(__file__).resolve().parent / "chroma_db"))
collection = client.get_or_create_collection(name="test_notes")


def ingest_file(file_path, course):
    documents = SimpleDirectoryReader(input_files=[str(file_path)], file_extractor={".pdf": PDFReader()}).load_data()
    nodes = [node for document in documents for node in chunk_document(document)]
    if not nodes:
        raise ValueError("No extractable text found in this document")
    file_name = Path(file_path).name
    existing = collection.get(where={"file_name": file_name}, include=[])["ids"]
    texts, embeddings, metadatas, ids = [], [], [], []
    # Finish extraction and all embedding calls before changing the existing index.
    for i, node in enumerate(nodes):
        response = ollama.embed(model="nomic-embed-text", input=node.text)
        texts.append(node.text)
        embeddings.append(response["embeddings"][0])
        metadatas.append({**node.metadata, "file_name": file_name, "course": course, "chunk_policy": "structure_v2"})
        ids.append(f"{file_name}-page-{node.metadata.get('page_label', 'unknown')}-chunk-{i}")
    collection.upsert(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)
    # Upsert alone leaves old IDs behind when the new document has fewer chunks.
    obsolete = sorted(set(existing) - set(ids))
    if obsolete:
        collection.delete(ids=obsolete)
    return len(nodes)
