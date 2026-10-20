from contextlib import asynccontextmanager
import json
import logging
from fastapi import FastAPI, HTTPException
from app.rag import ask_question, stream_question, get_courses, get_documents, delete_document
from pydantic import BaseModel, Field, field_validator
from fastapi.middleware.cors import CORSMiddleware
from fastapi import UploadFile, File
from pathlib import Path
from ingest_notes import ingest_file
from fastapi import Form
from fastapi.responses import FileResponse, StreamingResponse
from chat_db import create_chat, add_exchange, get_messages, get_chats, get_chat, initialize_database, rename_chat, delete_chat

NOTES_DIR = Path(__file__).resolve().parents[1] / "data" / "notes"


def note_path(file_name):
    if not file_name or "/" in file_name or "\\" in file_name or file_name in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid document name")
    path = (NOTES_DIR / file_name).resolve()
    if path.parent != NOTES_DIR.resolve():
        raise HTTPException(status_code=400, detail="Invalid document name")
    return path


@asynccontextmanager
async def lifespan(app):
    initialize_database()
    yield

app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str
    content: str

class QuestionRequest(BaseModel):
    question: str = Field(min_length=1)
    course: str | None = None
    history: list[ChatMessage] = Field(default_factory=list)
    chat_id: int | None = None

class ChatRequest(BaseModel):
    title: str = Field(min_length=1)
    course: str | None = None

@app.get("/")
def output():
    return {"message" : "It is a beautiful day!"}

@app.post("/ask")
def ask(request: QuestionRequest):
    history = request.history
    if request.chat_id is not None:
        if get_chat(request.chat_id) is None:
            raise HTTPException(status_code=404, detail="Chat not found")
        history = [ChatMessage(role=row[0], content=row[1]) for row in get_messages(request.chat_id)]

    result = ask_question(request.question, course=request.course, history=history)

    if request.chat_id is not None:
        add_exchange(request.chat_id, request.question, result["answer"])

    return result

@app.post("/upload")
async def upload_note(file: UploadFile = File(...), course: str = Form(...)):
    notes_dir = NOTES_DIR
    notes_dir.mkdir(parents=True, exist_ok=True)

    # if not file.filename.lower().endswith(".pdf"):
    #     return {
    #         "error: "Only PDF files are supported right now",
    #     }

    file_path = note_path(file.filename)

    contents = await file.read()

    file_path.write_bytes(contents)

    print("Saved path:", file_path)
    print("File exists:", file_path.exists())

    chunk_count = ingest_file(file_path, course)

    return {
        "filename": file.filename,
        "saved": True,
        "chunks_stored": chunk_count
    }

@app.get("/courses")
def courses():
    return {
        "courses": get_courses()
    }

@app.get("/documents")
def documents():
    return {
        "documents": get_documents()
    }

@app.delete("/documents/{file_name}")
def remove_document(file_name: str):
    file_path = note_path(file_name)
    delete_document(file_name)

    if file_path.exists():
        file_path.unlink()

    return {
        "deleted": True,
        "file": file_name
    }

@app.get("/chats")
def list_chats():
    rows = get_chats()

    chats = []

    for row in rows:
        chats.append({
            "id": row[0],
            "title": row[1],
            "course": row[2],
            "created_at": row[3]
        })

    return {"chats": chats}

@app.post("/chats")
def new_chat(request: ChatRequest):
    chat_id = create_chat(
        request.title,
        request.course
    )

    return {
        "id": chat_id,
        "title": request.title,
        "course": request.course
    }

@app.get("/chats/{chat_id}/messages")
def list_messages(chat_id: int):
    if get_chat(chat_id) is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    rows = get_messages(chat_id)

    messages = []

    for row in rows:
        messages.append({
            "role": row[0],
            "content": row[1],
            "created_at": row[2]
        })

    return {"messages": messages}


class RenameChatRequest(BaseModel):
    title: str = Field(min_length=1)

    @field_validator("title")
    @classmethod
    def validate_title(cls, title):
        title = title.strip()
        if not title:
            raise ValueError("Title cannot be blank")
        return title


@app.patch("/chats/{chat_id}")
def update_chat(chat_id: int, request: RenameChatRequest):
    if not rename_chat(chat_id, request.title):
        raise HTTPException(status_code=404, detail="Chat not found")
    return {"id": chat_id, "title": request.title}


@app.delete("/chats/{chat_id}")
def remove_chat(chat_id: int):
    if not delete_chat(chat_id):
        raise HTTPException(status_code=404, detail="Chat not found")
    return {"id": chat_id, "deleted": True}


@app.get("/documents/{file_name}/preview")
def preview_document(file_name: str):
    path = note_path(file_name)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Document not found")
    media_types = {".pdf": "application/pdf", ".txt": "text/plain; charset=utf-8"}
    media_type = media_types.get(path.suffix.lower())
    if media_type is None:
        raise HTTPException(status_code=415, detail="Preview supports PDF and text documents")
    # FileResponse serves file chunks/ranges; no PDF parsing, embeddings, or model calls.
    return FileResponse(path, media_type=media_type, filename=path.name,
                        content_disposition_type="inline",
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-store"})


@app.post("/ask/stream")
def ask_stream(request: QuestionRequest):
    history = request.history
    if request.chat_id is not None:
        if get_chat(request.chat_id) is None:
            raise HTTPException(status_code=404, detail="Chat not found")
        history = [ChatMessage(role=row[0], content=row[1]) for row in get_messages(request.chat_id)]

    def events():
        stream = stream_question(request.question, course=request.course, history=history)
        try:
            for event in stream:
                if event["type"] == "done" and request.chat_id is not None:
                    # Save only a complete exchange, before acknowledging completion to the browser.
                    add_exchange(request.chat_id, request.question, event["answer"])
                yield json.dumps(event, ensure_ascii=False) + "\n"
        except Exception:
            logging.getLogger("uvicorn.error").exception("Streaming answer failed")
            yield json.dumps({"type": "error", "message": "Could not finish the answer. Check the saved chat before retrying."}) + "\n"
        finally:
            if hasattr(stream, "close"):
                stream.close()

    return StreamingResponse(events(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})
