import chromadb
import ollama
from llama_index.llms.ollama import Ollama


client = chromadb.PersistentClient(path="chroma_db")

collection = client.get_or_create_collection(name="test_notes")

llm = Ollama(
        model="llama3.2:3b", 
        base_url="http://127.0.0.1:11434", 
        request_timeout=120.0
    )

def ask_question(question):
    query_embedding = ollama.embed(
        model="nomic-embed-text",
        input=question
        )["embeddings"][0]
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=2,
        include=["documents", "metadatas"])
    
    retrieved_docs = results["documents"][0]
    retrieved_metadata = results["metadatas"][0]
    print(retrieved_metadata)

    context ="\n\n".join(retrieved_docs)
    
    prompt = f"""
    Answer the question using only the context below.

    If the answer is not in the context, say:
    "I could not find that in the notes."

    Context:
    {context}

    Question:
    {question}
    """


    response = llm.complete(prompt)
    return {"answer": response.text,
            "sources": retrieved_metadata
            }