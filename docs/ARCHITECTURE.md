# Architecture

Cortex is a local-first RAG system. Everything runs on the developer's machine: the LLM through Ollama, vectors in PostgreSQL with pgvector, the API in FastAPI.

## Overview

```
                 User
                   │
                   ▼
          Frontend (React + Vite)      ← later phases
                   │
                   ▼
           FastAPI Backend
                   │
     ┌─────────────┼─────────────┐
     ▼             ▼             ▼
 Ingestion     Retrieval        LLM
  Service       Service       Service
     │             │             │
     ▼             ▼             ▼
  Parsers    PostgreSQL +     Ollama
  Chunker      pgvector
```

## Components

**Backend (FastAPI)** — Exposes the API: document upload, question answering (SSE streaming), and later collections, tools, and agents. Thin route handlers; all logic lives in services.

**Ingestion** — Takes a file, parses it to text, splits it into chunks, embeds each chunk, and stores chunk + vector + metadata (source, position) in Postgres. Metadata is stored from day one so citations can be added later without re-ingesting.

**Retrieval** — Embeds the query and returns the top-k most similar chunks via pgvector cosine similarity. Later phases extend this with full-text search (hybrid) and cross-encoder re-ranking without changing its interface.

**LLM Service** — Builds the prompt from retrieved context and streams the answer.

**Storage** — One PostgreSQL database for everything: documents, chunks, vectors (pgvector), logs, and later collections and users. Schema is managed with Alembic.

## Abstractions

Business logic depends on interfaces only. Each concrete provider is one implementation, swappable in one place:

| Interface           | First implementation      | Possible replacements        |
| ------------------- | ------------------------- | ---------------------------- |
| `LLMProvider`       | Ollama (Qwen3 4B)         | OpenAI-compatible API, Claude |
| `EmbeddingProvider` | Ollama (nomic-embed-text) | Any embedding API            |
| `VectorStore`       | pgvector                  | Qdrant, Chroma               |
| `DocumentParser`    | Plain text / Markdown     | PDF, DOCX, OCR               |

## Data flow

**Ingestion:** upload → parse → chunk → embed → store.

**Query:** question → embed → similarity search → top-k chunks → prompt with context → LLM → streamed answer.

## How to run

> The commands below land with step 1 of the plan; this section is kept current as the canonical way to run Cortex.

Prerequisites: Docker, Python 3.12+, [Ollama](https://ollama.com).

```bash
ollama pull qwen3:4b
ollama pull nomic-embed-text

docker compose -f docker/docker-compose.yml up -d

cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

The API is then available at `http://localhost:8000` with interactive docs at `http://localhost:8000/docs`.
