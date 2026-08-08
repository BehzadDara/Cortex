# Plan

Cortex is built in ordered steps. Each step ends with something runnable and demoable. Retrieval-quality steps (8, 9) are measured against the eval set from step 3 — never eyeballed.

## Steps

- [x] **1. Setup** — Docker Compose (PostgreSQL + Qdrant), FastAPI skeleton, Alembic migrations, Ollama with Qwen3 4B and nomic-embed-text.
- [x] **2. Minimal RAG** — Ingest `.txt` / `.md`: chunk → embed → store → retrieve top-k → answer with SSE streaming. Chunk metadata (source, position) stored from day one for future citations.
- [x] **3. Evaluation** — Golden set of 20–30 questions with expected answers and source chunks. Script reporting hit-rate@k. Every prompt/response/latency logged to a table.
- [x] **4. Documents** — PDF and DOCX parsing, file management, duplicate detection.
- [x] **5. Collections** — Group documents into collections, filter retrieval by collection.
- [x] **6. Website indexing** — Crawl a URL, clean HTML, chunk, index.
- [x] **7. Git repository indexing** — Clone a repo, code-aware chunking, index source and Markdown.
- [x] **8. Hybrid search** — Postgres full-text (`tsvector`) + Qdrant vector search, merged with reciprocal rank fusion. Measured: 97% → 100% hit rate@5.
- [x] **9. Re-ranking** — Cross-encoder narrows top-30 to top-5. Measured: hit@1 86% → 100%, MRR 0.925 → 1.000.
- [x] **10. Conversation memory** — Chat history, summarization, user preferences.
- [x] **11. Tool calling** — Document search, calculator, current time as callable tools via `/chat`. Qwen3 4B handles single-tool selection reliably.
- [x] **12. Agents** — Planner → retriever → reasoner workflow via `/agent`, returning the full trace.
- [x] **13. OCR & multimodal** — Images and scanned PDFs OCR'd by a local vision model (gemma3:4b); `/ask-image` for direct visual questions.
- [x] **14. Dashboard** — Indexed documents, latency, token usage — built on the logs kept since step 3. Ships with the full React frontend: chat (ask/chat/agent modes with streaming), documents, collections, dashboard.
- [x] **15. Production hardening** — Background jobs for crawl/repository indexing with status polling. API key auth and rate limiting were built, then removed for the single-user local setup; they return with deployment or multi-user support.
- [x] **16. LangGraph orchestration** — Agent rebuilt as a `StateGraph` with parallel retrieval fan-out, measured against the hand-rolled pipeline, then Chat + Agent merged into one streaming `/assistant` (model ⇄ tools cycle with live tool-step events). Postgres checkpointing makes runs resumable; `interrupt()` adds human-in-the-loop approval for web searches.

## Principles

- Frontend (React + Vite) lives in `frontend/`: Vite dev server proxies `/api` to the backend.
- Redis, MinIO, and any other infrastructure are added only when a step needs them.
- Decisions and lessons are recorded in `docs/DECISIONS.md` as they happen.

## Future ideas

Voice interface, Slack/Discord integration, browser extension, semantic caching, citation highlighting, local file watcher, incremental indexing.
