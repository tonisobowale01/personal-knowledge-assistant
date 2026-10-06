import ollama
import numpy as np

response = ollama.embed(
    model="nomic-embed-text",
    input="Round Robin gives each process a fixed time quantum."
)

embedding = response["embeddings"][0]
embedding_b = ollama.embed(model="nomic-embed-text",
    input="Each process gets a limited amount of CPU time before another process runs.")["embeddings"][0]
embedding_c = ollama.embed(model="nomic-embed-text", 
    input="Water freezes at zero degrees Celsius.")["embeddings"][0]

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

print(cosine_similarity(embedding, embedding_b))
print(cosine_similarity(embedding, embedding_c))
