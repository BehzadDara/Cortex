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

**Ingestion** — Takes a file (or a crawled web page), parses it to text plus any usable images, splits the text into chunks, stores chunk + metadata (source, position) in Postgres, embeds each chunk, and stores the vector in Qdrant with the chunk id as payload. Metadata is stored from day one so citations can be added later without re-ingesting. The crawler does a same-domain breadth-first crawl with a page cap, strips HTML boilerplate, and feeds each page through the same pipeline; unchanged pages are skipped by the content hash.

**Retrieval** — A three-stage funnel. Hybrid search: the query is embedded and sent to Qdrant (cosine similarity) while Postgres full-text search (`tsvector`, GIN-indexed) runs alongside; the two rankings are merged with reciprocal rank fusion into top-30 candidates. A cross-encoder (`ms-marco-MiniLM-L-6-v2`) then re-scores each candidate against the question and the top-5 survive. `HYBRID_SEARCH=false` and `RERANK=false` switch the stages off individually.

**LLM Service** — Talks to Ollama through the `LLMProvider` abstraction: streaming chat with tool definitions for the assistant, plain completions for titles and summaries. qwen3:4b (thinking enabled, reasoning discarded) answers; gemma3:4b handles titles and vision.

**Conversation memory** — `/assistant` accepts a `conversation_id` (a new conversation is created and streamed back otherwise). The model sees the conversation summary plus the most recent messages; older messages are folded into the summary incrementally after each exchange. Follow-ups need no query rewriting: if the seeded search misses, the model issues its own better-phrased searches with the history in view.

**Assistant** — `/assistant` is the single answering endpoint: a LangGraph graph (`route → retrieve → model ⇄ tools`). A `route` node asks the fast model whether the question needs the user's documents, judging follow-ups with the previous user question attached (measured at 100% on a 38-question routing golden set, `evals/routing.py`); document questions run the retrieval funnel with the raw question first — guaranteed grounding, streamed as a normal search step — while live-data, web, arithmetic, small-talk, and Cortex-stats questions jump straight to the model. From there the model orchestrates itself with tool definitions (`search_documents`, `web_search`, `web_image_search`, `calculator`, `world_clock`, `get_weather`, `crypto_price`, `kb_stats`, `usage_stats`, `generate_image`): answering directly when the seeded search suffices, decomposing into focused searches when it doesn't, and reaching for the web only when the relevance-gated document searches come back empty. Every step streams over SSE as typed events (`tool_call`, `tool_result`, `sources`, `widget`, `token`, `title`, `usage`, `saved`, `done`), and executed steps persist as JSONB on the assistant message so old chats replay their trace; the `saved` event carries the persisted assistant message id, written before `done` so the client can address the message immediately (conversation summarization runs after `done`). Tools with a visual payload — the world clock, weather, the 24-hour crypto chart, knowledge-base and usage stats, generated images, web image results, and the related-image galleries that document searches attach — return a widget alongside their text: streamed as a `widget` event, rendered as a live card under the answer, and persisted on the message like the steps, so reopened chats keep their cards; the model is instructed to answer in one short sentence beside a card rather than repeat its numbers. Every assistant answer takes a like/dislike via `PUT /messages/{id}/feedback` — an idempotent set that also switches or clears the vote (`null`), last state wins — persisted on the message, replayed with the chat, and counted on the dashboard. Any answer can also fork the conversation: `POST /messages/{id}/branch` deep-copies the prefix up to that answer (messages with their traces, sources, widgets, and usage; the summary too, unless the branch point falls inside the summarized region) into a new conversation that records its origin (`branched_from_id`, `branched_count`); the frontend renders a divider at the copy point linking back to the source, and deleting the source sets the link NULL without touching the branch. Retrieved passages are numbered globally per run (`[1]`, `[2]`, …) in a sources registry kept in graph state; the model cites passage numbers after claims, and the frontend renders them as chips that expand the exact chunk. Answers from runs that end with no sources are scrubbed of stray citation markers before persisting; the frontend additionally refuses to link any id that matches no source. LangGraph handles only control flow; nodes call the project's own provider abstractions. State checkpoints to Postgres after every node under a per-request thread id, which enables two things. Human-in-the-loop approval: before a `web_search` or `web_image_search` executes, the graph pauses via `interrupt()`, the stream emits an `approval` event and ends, and `POST /assistant/resume` continues the run from the checkpoint with the user's decision. Crash recovery: the conversation row tracks its active thread, and reopening a chat whose stream died calls `POST /assistant/continue`, which replays a `snapshot` of the work so far and re-runs the graph from the last completed node.

**Vision** — Images (`.png`, `.jpg`) are parsed by a local vision model that transcribes text and describes figures; the transcription then flows through the normal chunk → embed → index pipeline. PDFs without a text layer (scans) are rendered page by page and OCR'd the same way, capped at `ocr_max_pages`. `/ask-image` answers a question about an uploaded image directly, without indexing it.

**Knowledge images** — Pictures survive ingestion instead of being thrown away. Parsers return text plus extracted images: embedded images from PDFs and DOCX files, the original file for image uploads, and up to `crawl_max_images_per_page` pictures downloaded from each crawled page (collected after boilerplate stripping, so navigation logos never make it in). Every candidate is validated with PIL (format, minimum dimension, size cap) and deduplicated by content hash; the survivors — capped at `max_images_per_document` — are captioned by the vision model, written to disk through the `FileStore` abstraction (`backend/knowledge_images/`, served at `/knowledge-images/{filename}`), recorded in the `images` table with their caption, source URL, and position, and indexed by caption embedding in a second Qdrant collection keyed by the image row id. At answer time every document search also searches captions: hits are reranked against the question and relevance-gated (`image_min_relevance`), already-shown images are skipped, and the survivors stream as an `image_gallery` widget while a note in the tool result tells the model what the user is seeing. Deleting a document removes its image rows, vectors, and files. Web pictures come from the `ImageSearchProvider` (ddgs `.images()`) on two routes: every approved `web_search` that returns results also image-searches the same query and attaches the survivors — titles reranked against the query, gated by the same relevance threshold — so news answers arrive with their photos; and a separate approval-gated `web_image_search` tool covers explicit "show me pictures of…" requests. Both download the top hits through the same validation and store them on disk, so replayed conversations keep their galleries even after the remote image dies; a transient image-search failure is retried once and otherwise degrades to a text-only answer.

**Image generation** — The `generate_image` tool creates images from text through the `ImageGenerator` abstraction. The implementation calls Pollinations.ai, a free, keyless image API — the one deliberate exception to local-first, made after local diffusion proved too heavy next to the chat models on a 24 GB machine (see DECISIONS.md); only the draw-prompt leaves the machine, never documents or questions. The returned image is written to `backend/generated_images/` and served by a static mount at `/images/{filename}`; the widget persisted on the message stores only the filename, keeping conversation payloads light. Diagrams stay with mermaid — the system prompt reserves `generate_image` for pictures, photos, artwork, and illustrations.

Three earlier endpoints — `/ask` (the fixed RAG pipeline), `/chat` (a hand-rolled tool loop), and `/agent` (a hardcoded planner → retriever → reasoner pipeline, later rebuilt as a LangGraph fan-out graph) — were folded into the assistant and retired; DECISIONS.md records the comparisons. Every LLM call pins `num_ctx` explicitly so gathered evidence is never silently truncated by Ollama's small default context.

**Storage** — PostgreSQL is the source of truth: documents, chunks, images, logs, and later collections and users. Schema is managed with Alembic. Qdrant stores one vector per chunk in the `chunks` collection and one caption vector per image in the `images` collection — separate collections because point ids are the Postgres row ids, and chunk and image ids would collide. Keeping the stores in sync is the ingestion service's responsibility. Binary files live on disk behind the `FileStore` abstraction; MinIO stays out until a deployment needs it.

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
| `ImageSearchProvider` | ddgs (DuckDuckGo)       | Brave, SerpAPI               |
| `FileStore`         | Local disk                | MinIO, S3                    |
| `WeatherProvider`   | Open-Meteo                | Any weather API              |
| `MarketDataProvider`| CoinGecko                 | Any market data API          |
| `Reranker`          | ms-marco cross-encoder    | Any cross-encoder or API     |
| `ImageGenerator`    | Pollinations (free API)   | Local diffusion, ComfyUI, any image API |

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

The app runs at `http://localhost:5100` and proxies `/api/*` to the backend, so no CORS setup is needed. Views: Chat (one assistant conversation surface, with live tool-step cards, web-search approval prompts, mermaid code blocks rendered as downloadable SVG diagrams, widget cards — live clock, weather, crypto price chart, knowledge-base and usage stats, generated images, and related-image galleries from documents or the web — and like/dislike plus branch-from-here on every answer), Documents, Collections, and a Dashboard fed by `/stats` and `/logs` — counts, likes and dislikes, average latency, token usage, and recent prompt history.

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
