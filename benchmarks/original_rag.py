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

# all_data = collection.get(
#     include=["documents", "metadatas"]
# )

# for metadata in all_data["metadatas"]:
#     print(metadata)

def ask_question(question, course=None):
    query_embedding = ollama.embed(
        model="nomic-embed-text",
        input=question
        )["embeddings"][0]
    if course:
        results = collection.query(
        query_embeddings=[query_embedding],
        n_results=5,
        where={"course": course},
        include=["documents", "metadatas", "distances"]
    )
    else:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=5,
            include=["documents", "metadatas", "distances"]
        )
    # results = collection.query(
    #     query_embeddings=[query_embedding],
    #     n_results=5,
    #     include=["documents", "metadatas", "distances"])
    
    retrieved_docs = results["documents"][0]
    retrieved_metadata = results["metadatas"][0]
    best_distance = results["distances"][0][0]

    threshold = 1.1
    if best_distance > threshold:
        return {
            "answer": "I could not find that in the notes.",
            "sources": []
        }

    if not retrieved_docs:
        return{
            "answer": "I could not find that in the notes.",
            "sources": []
        }

    # print(retrieved_metadata)
    sources = []
    for metadata in retrieved_metadata:
        sources.append({
            "file": metadata.get("file_name"),
            "page": metadata.get("page_label")
        })

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
            "sources": sources
            }


# print(ask_question("What is a bus topology?", course="Networking"))
