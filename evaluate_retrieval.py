import chromadb
import ollama

client = chromadb.PersistentClient(path="chroma_db")
collection = client.get_or_create_collection(name="test_notes")

tests = [
    {
        "question": "What is a bus topology?",
        "course": "Networking",
        "expected_keyword": "bus"
    },
    {
        "question": "How are devices connected in a bus network?",
        "course": "Networking",
        "expected_keyword": "bus"
    },
    {
        "question": "What is FCFS?",
        "course": "Operating Systems",
        "expected_keyword": "FCFS"
    },
    {
        "question": "Which scheduler runs processes in arrival order?",
        "course": "Operating Systems",
        "expected_keyword": "FCFS"
    },
    {
        "question": "What are the disadvantages of SJF?",
        "course": "Operating Systems",
        "expected_keyword": "starvation"
    },
    {
        "question": "Why can short-job-first be unfair to long processes?",
        "course": "Operating Systems",
        "expected_keyword": "starvation"
    },
    {
        "question": "What is photosynthesis?",
        "course": "Operating Systems",
        "expected_keyword": None
    }
]

passed = 0

for test in tests:
    question = test["question"]
    course = test["course"]
    expected_keyword = test["expected_keyword"]

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

    retrieved_docs = results["documents"][0]
    best_distance = results["distances"][0][0]

    threshold = 1.1

    if expected_keyword is None:
        found = best_distance > threshold
    else:
        found = ( best_distance <= threshold and any(
                expected_keyword.lower() in doc.lower()
                for doc in retrieved_docs
            ))
    

    if found:
        passed += 1
        print(f"PASS - {question}\n")
    else:
        print(f"FAIL - {question}\n")

total = len(tests)
accuracy = passed / total * 100

print(f"\nPassed: {passed}/{total}")
print(f"Retrieval accuracy: {accuracy:.1f}%")