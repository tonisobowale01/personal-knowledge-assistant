from pathlib import Path
import chromadb
import ollama
from llama_index.core import SimpleDirectoryReader
from llama_index.readers.file import PDFReader
from llama_index.core.node_parser import SentenceSplitter

client = chromadb.PersistentClient(path=str(Path(__file__).resolve().parent / "chroma_db"))

collection = client.get_or_create_collection(name="test_notes")


def ingest_file(file_path, course):
    parser = PDFReader()

    documents = SimpleDirectoryReader(input_files=[str(file_path)], file_extractor={".pdf": parser}).load_data()

    splitter = SentenceSplitter(chunk_size=512, chunk_overlap=50)
    nodes = splitter.get_nodes_from_documents(documents)

    print(f"Created {len(nodes)} nodes")

    documents_to_store = []
    embeddings = []
    metadatas = []
    ids = []

    for i, node in enumerate(nodes):
        text = node.text
        file_name = node.metadata.get("file_name", "unknown")
        page = node.metadata.get("page_label", "unknown")

        chunk_id = f"{file_name}-page-{page}-chunk-{i}"

        response = ollama.embed(
            model="nomic-embed-text",
            input=text
        )

        metadata = dict(node.metadata)
        metadata["course"] = course

        documents_to_store.append(text)
        embeddings.append(response["embeddings"][0])
        metadatas.append(metadata)
        ids.append(chunk_id)


    collection.upsert(
        ids=ids,
        documents=documents_to_store,
        embeddings=embeddings,
        metadatas=metadatas
    )

    return len(nodes)

# print(ingest_file("data/notes/networking summary.pdf"))