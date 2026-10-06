




# results = collection.query(
#     query_embeddings=[query_embedding],
#     n_results=2
# )

# print(results["documents"][0])
# retrieved_docs = results["documents"][0]
# context ="\n\n".join(retrieved_docs)

# prompt = f"""
# Answer the question using only the context below.

# If the answer is not in the context, say:
# "I could not find that in the notes."

# Context:
# {context}

# Question:
# How does Round Robin scheduling work?
# """

# llm = Ollama(
#     model="llama3.2:3b", 
#     base_url="http://127.0.0.1:11434", 
#     request_timeout=120.0
# )

# response = llm.complete(prompt)
# print(response.text)