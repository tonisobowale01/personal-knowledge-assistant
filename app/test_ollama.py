import ollama

response = ollama.generate(
    model="llama3.2:3b",
    prompt="Say hello in one sentence."
)

print(response["response"])