from fastapi import FastAPI
from app.rag import ask_question
from pydantic import BaseModel

app = FastAPI()

class QuestionRequest(BaseModel):
    question: str

@app.get("/")
def output():
    return {"message" : "It is a beautiful day!"}

@app.post("/ask")
def ask(request: QuestionRequest):
    answer = ask_question(request.question)
    return answer