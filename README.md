# Cortex

> Your second brain.

Cortex is a local-first AI knowledge assistant. Upload your documents, index websites and repositories, and ask questions — answered by a local LLM, grounded in your own data.

It is also a learning project: it starts as the simplest possible RAG application and grows step by step into a production-like AI platform with hybrid search, re-ranking, memory, tool calling, agents, and evaluation.

## Stack

- **Backend** — Python, FastAPI
- **Database** — PostgreSQL + pgvector
- **LLM** — Ollama (Qwen3 4B)
- **Embeddings** — nomic-embed-text
- **Frontend** — React + Vite (later phases)

## Documentation

- [Plan](docs/PLAN.md) — the roadmap, step by step
- [Architecture](docs/ARCHITECTURE.md) — system design and how to run it

## Status

🚧 Early days — currently at step 2 of the [plan](docs/PLAN.md).
