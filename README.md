# Cortex

> Your second brain.

Cortex is a local-first AI knowledge assistant. Upload your documents, index websites and repositories, and ask questions — answered by a local LLM, grounded in your own data, with every tool step visible as it works.

It is also a learning project: it started as the simplest possible RAG application and grew step by step into a full AI platform — hybrid search with re-ranking, conversation memory, an evaluation harness, OCR, background jobs, and a LangGraph-orchestrated assistant with streaming tool steps, durable Postgres checkpoints, and human-in-the-loop web-search approval.

## Highlights

- **One assistant** — every question runs a guaranteed document search first, then the model decides: answer directly, decompose into focused searches, or reach for the web (with your approval), a calculator, or the clock. Each step streams live and is replayable from history.
- **Measured retrieval** — hybrid search (vector + full-text, reciprocal rank fusion) plus cross-encoder re-ranking, tuned against a golden eval set: 100% hit@1, MRR 1.000 on the current corpus.
- **Everything local** — Ollama for LLM, embeddings, and vision; Qdrant for vectors; PostgreSQL as the source of truth. No API keys, no cloud.
- **Everything replaceable** — LLM, embeddings, vector store, parsers, reranker, and web search all sit behind interfaces; swapping a provider touches one file.

## Stack

- **Backend** — Python, FastAPI, LangGraph
- **Database** — PostgreSQL
- **Vector DB** — Qdrant
- **LLM** — Ollama (Qwen3 4B; Gemma3 4B for titles and vision)
- **Embeddings** — nomic-embed-text
- **Frontend** — React + Vite

## Documentation

- [Plan](docs/PLAN.md) — the roadmap, step by step
- [Architecture](docs/ARCHITECTURE.md) — system design and how to run it
- [Decisions](docs/DECISIONS.md) — a lab notebook of measurements, trade-offs, and lessons
