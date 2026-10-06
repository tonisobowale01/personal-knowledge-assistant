import chromadb
import ollama
from llama_index.core import SimpleDirectoryReader
from llama_index.readers.file import PDFReader
from llama_index.core.node_parser import SentenceSplitter
# import os

# print(os.getcwd())
# print(os.path.exists("data"))
# print(os.path.exists("data/notes"))
# print(os.listdir("data"))


client = chromadb.PersistentClient(path="chroma_db")

collection = client.get_or_create_collection(name="test_notes")

parser = PDFReader()

documents = SimpleDirectoryReader(input_dir="data/notes", file_extractor={".pdf": parser}).load_data()

# print(f"Loaded {len(documents)} documets/pages")

splitter = SentenceSplitter(chunk_size=512, chunk_overlap=50)
nodes = splitter.get_nodes_from_documents(documents)

# print(f"Loaded {len(documents)} documents/pages")
# print(f"Created {len(nodes)} nodes")

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

    if file_name == "networking summary.pdf":
        metadata["course"] = "Networking"
    elif file_name == "os_sample.txt":
        metadata["course"] = "Operating Systems"

    documents_to_store.append(text)
    embeddings.append(response["embeddings"][0])
    metadatas.append(metadata)
    ids.append(chunk_id)

# print(len(documents_to_store))
# print(len(embeddings))
# print(len(metadatas))
# print(len(ids))

collection.upsert(
    ids=ids,
    documents=documents_to_store,
    embeddings=embeddings,
    metadatas=metadatas
)

print("Stored chunks:", collection.count())