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

**Assistant** — `/assistant` is the agentic endpoint: a LangGraph two-node cycle (`model ⇄ tools`) where the model receives tool definitions (`search_documents`, `web_search`, `calculator`, `current_time`) and orchestrates itself — decomposing complex questions into several searches, falling back to the web when the relevance-gated document search returns nothing. Every step streams over SSE as typed events (`tool_call`, `tool_result`, `token`, `title`, `done`), and executed steps persist as JSONB on the assistant message so old chats replay their trace. LangGraph handles only control flow; nodes call the project's own provider abstractions. State checkpoints to Postgres after every node under a per-request thread id, which enables human-in-the-loop approval: before a `web_search` executes, the graph pauses via `interrupt()`, the stream emits an `approval` event and ends, and `POST /assistant/resume` continues the run from the checkpoint with the user's decision. `/ask` remains the fixed RAG pipeline.

**Vision** — Images (`.png`, `.jpg`) are parsed by a local vision model that transcribes text and describes figures; the transcription then flows through the normal chunk → embed → index pipeline. PDFs without a text layer (scans) are rendered page by page and OCR'd the same way, capped at `ocr_max_pages`. `/ask-image` answers a question about an uploaded image directly, without indexing it.

Two earlier endpoints — `/chat` (a hand-rolled tool loop) and `/agent` (a hardcoded planner → retriever → reasoner pipeline, later rebuilt as a LangGraph fan-out graph) — were measured against the assistant and retired; DECISIONS.md records the comparison. Every LLM call pins `num_ctx` explicitly so gathered evidence is never silently truncated by Ollama's small default context.

**Storage** — PostgreSQL is the source of truth: documents, chunks, logs, and later collections and users. Schema is managed with Alembic. Qdrant stores one vector per chunk; keeping the two in sync is the ingestion service's responsibility.

## Abstractions

Business logic depends on interfaces only. Each concrete provider is one implementation, swappable in one place:

| Interface           | First implementation      | Possible replacements        |
| ------------------- | ------------------------- | ---------------------------- |
| `LLMProvider`       | Ollama (Qwen3 4B)         | OpenAI-compatible API, Claude |
| `EmbeddingProvider` | Ollama (nomic-embed-text) | Any embedding API            |
| `VectorStore`       | Qdrant                    | pgvector, Chroma             |
| `DocumentParser`    | txt/md, PDF, DOCX, images | HTML, more formats           |
| `VisionProvider`    | Ollama (gemma3:4b)        | Any vision-capable API       |
| `WebSearchProvider` | ddgs (DuckDuckGo)         | Tavily, Brave, SearXNG       |
| `Reranker`          | ms-marco cross-encoder    | Any cross-encoder or API     |

LangGraph sits outside this table on purpose: it orchestrates control flow (the assistant's model ⇄ tools cycle, checkpointing, interrupts) but never talks to a model or database itself — swapping any provider still touches one file.

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

The API is then available at `http://localhost:8100` (start uvicorn with `--port 8100`) with interactive docs at `http://localhost:8100/docs`. `GET /health` reports the status of Postgres, Qdrant, and Ollama.

For the frontend:

```bash
cd frontend
npm install
npm run dev
```

The app runs at `http://localhost:5100` and proxies `/api/*` to the backend, so no CORS setup is needed. Views: Chat (ask and assistant modes, with live tool-step cards and web-search approval prompts), Documents, Collections, and a Dashboard fed by `/stats` and `/logs` — counts, average latency, token usage, and recent prompt history.

## Background jobs

Website and repository indexing run as background jobs: the endpoint returns `202` with a job id immediately and the work runs after the response (FastAPI `BackgroundTasks`, in-process; a task queue like Celery is the production upgrade). `GET /jobs/{id}` reports pending → running → done/failed with a result summary.

The API is currently unauthenticated: Cortex runs as a single-user local tool. API keys with rate limiting were built in step 15 and deliberately removed afterwards (see DECISIONS.md); they return when the app is deployed or becomes multi-user.

## Evaluation

`backend/evals/golden.json` holds golden questions with expected answers and source chunks. Run the eval after any change to chunking, retrieval, or prompts:

```bash
cd backend
.venv/bin/python -m evals.run                  # retrieval + generation
.venv/bin/python -m evals.run --retrieval-only # fast, no LLM
```

Every `/ask` request is logged to the `prompt_logs` table with question, full prompt, response, model, and latency.
