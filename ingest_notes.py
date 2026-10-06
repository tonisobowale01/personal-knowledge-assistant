import chromadb
import ollama

client = chromadb.PersistentClient(path="chroma_db")

collection = client.get_or_create_collection(name="test_notes")

with open("data/notes/os_sample.txt", "r", encoding="utf-8") as file:
    text = file.read()
    chunks = text.split("\n\n")

embeddings = []
ids = [str(i) for i in range(len(chunks))]

metadatas = []

for i, chunk in enumerate(chunks):
    metadatas.append({
        "source": "os_sample.txt",
        "course": "Operating Systems",
        "chunk": i
    })

for chunk in chunks:
    response = ollama.embed(
        model="nomic-embed-text",
        input=chunk
    )
    embeddings.append(response["embeddings"][0])

collection.add(
    ids=ids,
    documents=chunks,
    embeddings=embeddings,
    metadatas=metadatas
)

print(f"Stored {len(chunks)} chunks.")