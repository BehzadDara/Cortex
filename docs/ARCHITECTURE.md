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

**Backend (FastAPI)** — Exposes the API: document upload, collections, the streaming assistant, image questions, jobs, and stats. Thin route handlers; all logic lives in services.

**Ingestion** — Takes a file (or a crawled web page), parses it to text, splits it into chunks, stores chunk + metadata (source, position) in Postgres, embeds each chunk, and stores the vector in Qdrant with the chunk id as payload. Metadata is stored from day one so citations can be added later without re-ingesting. The crawler does a same-domain breadth-first crawl with a page cap, strips HTML boilerplate, and feeds each page through the same pipeline; unchanged pages are skipped by the content hash.

**Retrieval** — A three-stage funnel. Hybrid search: the query is embedded and sent to Qdrant (cosine similarity) while Postgres full-text search (`tsvector`, GIN-indexed) runs alongside; the two rankings are merged with reciprocal rank fusion into top-30 candidates. A cross-encoder (`ms-marco-MiniLM-L-6-v2`) then re-scores each candidate against the question and the top-5 survive. `HYBRID_SEARCH=false` and `RERANK=false` switch the stages off individually.

**LLM Service** — Talks to Ollama through the `LLMProvider` abstraction: streaming chat with tool definitions for the assistant, plain completions for titles and summaries. qwen3:4b (thinking enabled, reasoning discarded) answers; gemma3:4b handles titles and vision.

**Conversation memory** — `/assistant` accepts a `conversation_id` (a new conversation is created and streamed back otherwise). The model sees the conversation summary plus the most recent messages; older messages are folded into the summary incrementally after each exchange. Follow-ups need no query rewriting: if the seeded search misses, the model issues its own better-phrased searches with the history in view.

**Assistant** — `/assistant` is the single answering endpoint: a LangGraph graph (`route → retrieve → model ⇄ tools`). A `route` node asks the fast model whether the question needs the user's documents, judging follow-ups with the previous user question attached (measured at 100% on a 38-question routing golden set, `evals/routing.py`); document questions run the retrieval funnel with the raw question first — guaranteed grounding, streamed as a normal search step — while live-data, web, arithmetic, small-talk, and Cortex-stats questions jump straight to the model. From there the model orchestrates itself with tool definitions (`search_documents`, `web_search`, `calculator`, `world_clock`, `get_weather`, `crypto_price`, `kb_stats`, `usage_stats`): answering directly when the seeded search suffices, decomposing into focused searches when it doesn't, and reaching for the web only when the relevance-gated document searches come back empty. Every step streams over SSE as typed events (`tool_call`, `tool_result`, `sources`, `widget`, `token`, `title`, `usage`, `done`), and executed steps persist as JSONB on the assistant message so old chats replay their trace. Tools with a visual payload — the world clock, weather, the 24-hour crypto chart, knowledge-base and usage stats — return a widget alongside their text: streamed as a `widget` event, rendered as a live card under the answer, and persisted on the message like the steps, so reopened chats keep their cards; the model is instructed to answer in one short sentence beside a card rather than repeat its numbers. Retrieved passages are numbered globally per run (`[1]`, `[2]`, …) in a sources registry kept in graph state; the model cites passage numbers after claims, and the frontend renders them as chips that expand the exact chunk. Answers from runs that end with no sources are scrubbed of stray citation markers before persisting; the frontend additionally refuses to link any id that matches no source. LangGraph handles only control flow; nodes call the project's own provider abstractions. State checkpoints to Postgres after every node under a per-request thread id, which enables two things. Human-in-the-loop approval: before a `web_search` executes, the graph pauses via `interrupt()`, the stream emits an `approval` event and ends, and `POST /assistant/resume` continues the run from the checkpoint with the user's decision. Crash recovery: the conversation row tracks its active thread, and reopening a chat whose stream died calls `POST /assistant/continue`, which replays a `snapshot` of the work so far and re-runs the graph from the last completed node.

**Vision** — Images (`.png`, `.jpg`) are parsed by a local vision model that transcribes text and describes figures; the transcription then flows through the normal chunk → embed → index pipeline. PDFs without a text layer (scans) are rendered page by page and OCR'd the same way, capped at `ocr_max_pages`. `/ask-image` answers a question about an uploaded image directly, without indexing it.

Three earlier endpoints — `/ask` (the fixed RAG pipeline), `/chat` (a hand-rolled tool loop), and `/agent` (a hardcoded planner → retriever → reasoner pipeline, later rebuilt as a LangGraph fan-out graph) — were folded into the assistant and retired; DECISIONS.md records the comparisons. Every LLM call pins `num_ctx` explicitly so gathered evidence is never silently truncated by Ollama's small default context.

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
| `WeatherProvider`   | Open-Meteo                | Any weather API              |
| `MarketDataProvider`| CoinGecko                 | Any market data API          |
| `Reranker`          | ms-marco cross-encoder    | Any cross-encoder or API     |

LangGraph sits outside this table on purpose: it orchestrates control flow (the assistant's model ⇄ tools cycle, checkpointing, interrupts) but never talks to a model or database itself — swapping any provider still touches one file.

## Data flow

**Ingestion:** upload → parse → chunk → embed → store.

**Query:** question → retrieval funnel (hybrid search → rerank → relevance gate) seeded as the first tool step → model answers or loops with more tools → streamed answer with the full step trace.

## How to run

Prerequisites: Docker, Python 3.12+, [Ollama](https://ollama.com).

```bash
ollama pull qwen3:4b
ollama pull gemma3:4b
ollama pull nomic-embed-text

docker compose -f docker/docker-compose.yml up -d

cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --port 8100 --reload
```

The API is then available at `http://localhost:8100` with interactive docs at `http://localhost:8100/docs`. `GET /health` reports the status of Postgres, Qdrant, and Ollama.

For the frontend:

```bash
cd frontend
npm install
npm run dev
```

The app runs at `http://localhost:5100` and proxies `/api/*` to the backend, so no CORS setup is needed. Views: Chat (one assistant conversation surface, with live tool-step cards, web-search approval prompts, mermaid code blocks rendered as downloadable SVG diagrams, and widget cards — live clock, weather, crypto price chart, knowledge-base and usage stats), Documents, Collections, and a Dashboard fed by `/stats` and `/logs` — counts, average latency, token usage, and recent prompt history.

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

Every `/assistant` exchange is logged to the `prompt_logs` table with question, a transcript of the tool steps, response, model, latency, and token counts summed over the run's model rounds. Token counts and the run's wall clock — each graph node times itself into state, so segments of an interrupted run sum and approval wait time is excluded — persist on the assistant message and render under the answer.
