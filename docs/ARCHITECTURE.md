# Architecture

Cortex is a local-first RAG system. Everything runs on the developer's machine: the LLM through Ollama, vectors in Qdrant, relational data in PostgreSQL, the API in FastAPI.

## Overview

```
                 User
                   │
                   ▼
          Frontend (React + Vite)
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
  Parsers      Qdrant         Ollama
  Chunker     (vectors)
                   │
                   ▼
              PostgreSQL
       (documents, chunks, logs)
```

## Components

**Backend (FastAPI)** — Exposes the API: document upload, question answering (SSE streaming), and later collections, tools, and agents. Thin route handlers; all logic lives in services.

**Ingestion** — Takes a file (or a crawled web page), parses it to text, splits it into chunks, stores chunk + metadata (source, position) in Postgres, embeds each chunk, and stores the vector in Qdrant with the chunk id as payload. Metadata is stored from day one so citations can be added later without re-ingesting. The crawler does a same-domain breadth-first crawl with a page cap, strips HTML boilerplate, and feeds each page through the same pipeline; unchanged pages are skipped by the content hash.

**Retrieval** — A three-stage funnel. Hybrid search: the query is embedded and sent to Qdrant (cosine similarity) while Postgres full-text search (`tsvector`, GIN-indexed) runs alongside; the two rankings are merged with reciprocal rank fusion into top-30 candidates. A cross-encoder (`ms-marco-MiniLM-L-6-v2`) then re-scores each candidate against the question and the top-5 survive. `HYBRID_SEARCH=false` and `RERANK=false` switch the stages off individually.

**LLM Service** — Builds the prompt from retrieved context and streams the answer.

**Conversation memory** — `/ask` accepts a `conversation_id` (a new one is created and returned in the `X-Conversation-Id` header otherwise). Follow-up questions are rewritten into standalone questions by the LLM before retrieval. The answer prompt carries the conversation summary plus the most recent messages; older messages are folded into the summary incrementally after each exchange.

**Storage** — PostgreSQL is the source of truth: documents, chunks, logs, and later collections and users. Schema is managed with Alembic. Qdrant stores one vector per chunk; keeping the two in sync is the ingestion service's responsibility.

## Abstractions

Business logic depends on interfaces only. Each concrete provider is one implementation, swappable in one place:

| Interface           | First implementation      | Possible replacements        |
| ------------------- | ------------------------- | ---------------------------- |
| `LLMProvider`       | Ollama (Qwen3 4B)         | OpenAI-compatible API, Claude |
| `EmbeddingProvider` | Ollama (nomic-embed-text) | Any embedding API            |
| `VectorStore`       | Qdrant                    | pgvector, Chroma             |
| `DocumentParser`    | txt/md, PDF, DOCX         | HTML, OCR                    |

## Data flow

**Ingestion:** upload → parse → chunk → embed → store.

**Query:** question → embed → similarity search → top-k chunks → prompt with context → LLM → streamed answer.

## How to run

Prerequisites: Docker, Python 3.12+, [Ollama](https://ollama.com).

```bash
ollama pull qwen3:4b
ollama pull nomic-embed-text

docker compose -f docker/docker-compose.yml up -d

cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
```

The API is then available at `http://localhost:8000` with interactive docs at `http://localhost:8000/docs`. `GET /health` reports the status of Postgres, Qdrant, and Ollama.

## Evaluation

`backend/evals/golden.json` holds golden questions with expected answers and source chunks. Run the eval after any change to chunking, retrieval, or prompts:

```bash
cd backend
.venv/bin/python -m evals.run                  # retrieval + generation
.venv/bin/python -m evals.run --retrieval-only # fast, no LLM
```

Every `/ask` request is logged to the `prompt_logs` table with question, full prompt, response, model, and latency.
