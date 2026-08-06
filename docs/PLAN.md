# Plan

Cortex is built in ordered steps. Each step ends with something runnable and demoable. Retrieval-quality steps (8, 9) are measured against the eval set from step 3 — never eyeballed.

## Steps

- [x] **1. Setup** — Docker Compose (PostgreSQL + pgvector), FastAPI skeleton, Alembic migrations, Ollama with Qwen3 4B and nomic-embed-text.
- [ ] **2. Minimal RAG** — Ingest `.txt` / `.md`: chunk → embed → store → retrieve top-k → answer with SSE streaming. Chunk metadata (source, position) stored from day one for future citations.
- [ ] **3. Evaluation** — Golden set of 20–30 questions with expected answers and source chunks. Script reporting hit-rate@k. Every prompt/response/latency logged to a table.
- [ ] **4. Documents** — PDF and DOCX parsing, file management, duplicate detection.
- [ ] **5. Collections** — Group documents into collections, filter retrieval by collection.
- [ ] **6. Website indexing** — Crawl a URL, clean HTML, chunk, index.
- [ ] **7. Git repository indexing** — Clone a repo, code-aware chunking, index source and Markdown.
- [ ] **8. Hybrid search** — Postgres full-text (`tsvector`) + vector search, merged. Measured.
- [ ] **9. Re-ranking** — Cross-encoder narrows top-30 to top-5. Measured.
- [ ] **10. Conversation memory** — Chat history, summarization, user preferences.
- [ ] **11. Tool calling** — Document search, calculator, current time as callable tools. Larger model (8B+) or API provider behind the existing LLM abstraction.
- [ ] **12. Agents** — Planner → retriever → reasoner workflow.
- [ ] **13. OCR & multimodal** — Scanned PDFs, images, diagrams.
- [ ] **14. Dashboard** — Indexed documents, latency, token usage — built on the logs kept since step 3.
- [ ] **15. Production hardening** — Auth, users, API keys, rate limiting, background jobs.

## Principles

- Frontend (React + Vite) joins once the API is worth a UI — around step 4–5.
- Redis, MinIO, and any other infrastructure are added only when a step needs them.
- Decisions and lessons are recorded in `docs/DECISIONS.md` as they happen.

## Future ideas

Voice interface, Slack/Discord integration, browser extension, semantic caching, citation highlighting, local file watcher, incremental indexing.
