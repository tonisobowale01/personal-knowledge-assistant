# Personal Knowledge Assistant (Ash)

A local Retrieval-Augmented Generation (RAG) application that lets users ask questions about their school notes and receive answers grounded in those notes.

The project uses FastAPI for the backend API, LlamaIndex for document processing and RAG orchestration, Ollama for running local language and embedding models, `nomic-embed-text` for embeddings, and ChromaDB for vector storage and retrieval.

## Architecture

The system has two main pipelines:

### Ingestion
Notes -> chunking -> embeddings -> ChromaDB

### Query
Question -> embedding -> retrieve relevant chunks -> LLM -> answer

## Tech Stack

- Python
- FastAPI
- LlamaIndex
- Ollama
- llama3.2:3b
- nomic-embed-text
- ChromaDB

## Current Features

- Runs a local LLM with Ollama
- Generates embeddings with `nomic-embed-text`
- Stores and retrieves note chunks using ChromaDB
- Uses persistent vector storage
- Retrieves semantically relevant note sections
- Generates answers grounded in retrieved context
- Returns source metadata with answers
- Exposes the RAG system through a FastAPI `/ask` endpoint
- Loads PDF documents with LlamaIndex
- Splits PDF content into overlapping chunks while preserving metadata

## Current Limitations

- PDF ingestion is still being integrated into the main ingestion pipeline
- Image-heavy and scanned PDFs are not yet fully supported
- No frontend yet
- No authentication or multi-user support
- Retrieval quality has not yet been formally evaluated