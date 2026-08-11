# Cortex

Local-first AI knowledge assistant. A learning project that starts as minimal RAG and grows, phase by phase, into a full AI platform. The roadmap lives in [docs/PLAN.md](docs/PLAN.md), the system design in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Rules

- **No code comments.** Code must explain itself through naming and structure. If a comment feels necessary, rewrite the code until it isn't.
- **Clean code.** Small functions, meaningful names, single responsibility. Readability beats cleverness every time.
- **Everything replaceable is behind an abstraction.** LLM, embeddings, vector store, parsers — business logic depends on interfaces, never on Ollama, Qdrant, or any concrete provider directly. Swapping a provider must touch one file.
- **Keep it simple.** No premature infrastructure, no speculative features, no config for problems we don't have yet. Add a component only when something actually uses it.
- **One phase at a time.** Each phase ends runnable and demoable before the next begins.
- **Measure retrieval changes.** Once the eval set exists, any change to chunking, search, or ranking is judged by it — not by eyeballing.

## Structure

- `backend/` — FastAPI application (Python)
- `frontend/` — React + Vite
- `docker/` — compose files
- `docs/` — plan and architecture

## Stack

Python + FastAPI, PostgreSQL for relational data, Qdrant for vectors, Ollama (qwen3:4b for answers, gemma3:4b for titles and vision, nomic-embed-text for embeddings), Pollinations (free keyless API) for image generation — a local Ollama implementation (x/z-image-turbo, needs Ollama 0.32.5) sits behind the same abstraction as an alternative — LangGraph for assistant orchestration only, React + Vite for the frontend. Redis and MinIO are deliberately absent until a feature needs them.
