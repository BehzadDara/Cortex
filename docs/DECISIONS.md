# Decisions

A running log of technical decisions and lessons, newest first.

## 2026-08-06 — Web search fallback needs a relevance gate

Added free web search (ddgs/DuckDuckGo, no API key) behind a `WebSearchProvider` abstraction: a `web_search` tool in chat mode, and a fallback in the agent when documents have nothing. First attempt never triggered — vector search has no concept of "no relevant results"; it always returns the nearest chunks, so findings were never empty. Fix: the cross-encoder already scores every candidate, and irrelevant pairs score below zero, so the agent now filters evidence by rerank score (`agent_min_relevance`, default 0.0) and falls back to the web only when nothing relevant survives. Lesson: "top-k" is not "relevant-k" — thresholds must come from a model that actually measures relevance. Web snippets are shallow evidence; fetching full pages for top results is the known upgrade.

## 2026-08-06 — API keys removed after being built

Step 15 added API key auth (SHA-256 hashed at rest) and per-key rate limiting. Both worked, and both were removed the same day: for a single-user tool running on localhost, pasting a key into your own frontend is pure friction with no threat model behind it. The lesson kept: auth design (hash keys, meter usage per identity) and the discipline of removing features that don't pay their way. The git history preserves the implementation for when deployment or multi-user support makes it relevant.

## 2026-08-06 — Cross-encoder re-ranking measured

Funnel: hybrid retrieval fetches top-30 candidates, `cross-encoder/ms-marco-MiniLM-L-6-v2` re-scores them, top-5 survive. Measured on 29 golden questions:

| Mode | hit@1 | MRR | avg retrieval |
| --- | --- | --- | --- |
| hybrid only | 25/29 = 86% | 0.925 | 61 ms |
| hybrid + rerank | 29/29 = 100% | 1.000 | 227 ms |

hit rate@5 was already 100%, so the win shows in ranking quality: every answer now sits at position 1, meaning the LLM sees the best evidence first. Price: ~170 ms of local model inference per query. `RERANK=false` disables it. The cross-encoder runs inside the backend process via sentence-transformers — the first dependency that executes a neural network in-process instead of behind Ollama's API.

## 2026-08-06 — Hybrid search measured

Corpus at 29 golden questions over ~100 chunks (examples + crawled pages + the Cortex repo itself):

| Mode | hit rate@5 | avg retrieval |
| --- | --- | --- |
| vector only | 28/29 = 97% | 43 ms |
| hybrid (RRF) | 29/29 = 100% | 50 ms |

The rescued question was "What is the Great Red Spot?" — an exact phrase that full-text search finds at rank 1 while vector search had let it slip out of top-5 as the corpus grew. Two side lessons: eval scoring must normalize whitespace (pypdf wraps lines mid-phrase, which made a rank-1 hit look like a MISS), and `plainto_tsquery` ANDs all terms, so one absent word empties the keyword result — the vector leg covers those cases, which is exactly why hybrid works.

## 2026-08-06 — Schema migrations are not data migrations

Adding `content_hash` for duplicate detection looked done once the column migrated — but documents ingested before the migration had NULL hashes, so re-uploading one of them slipped past the duplicate check. Lesson: a new constraint only protects rows written after it; existing rows need a backfill (or, in dev, deletion and re-ingestion). The column stays nullable because the original text cannot be reconstructed from overlapping chunks.

## 2026-08-06 — Evaluation baseline

First eval run over 3 documents (6 chunks), 25 golden questions, qwen3:4b with thinking enabled:

| Metric | Value |
| --- | --- |
| hit rate@5 | 25/25 = 100% |
| answer accuracy | 25/25 = 100% |
| avg retrieval | 39 ms |
| avg generation | 7.6 s |

With only 6 chunks and top-5 retrieval, a perfect score is expected — the numbers become meaningful as the corpus grows. Every retrieval change from here on is judged by re-running `python -m evals.run`.

## 2026-08-06 — Run Qwen3 with thinking enabled

Qwen3 is a reasoning model. Disabling thinking (`think: false`) did not suppress it — reasoning leaked into the answer stream. Running it as designed (`think: true`) makes Ollama separate reasoning into a `thinking` field, which the LLM provider discards, streaming only the clean answer. Cost: a few seconds of silent thinking per answer. Benefit: better answers, clean output.

## 2026-08-06 — Qdrant instead of pgvector

Started with pgvector to keep everything in one database, then switched to Qdrant to learn a dedicated vector database from day one. Postgres remains the source of truth (documents, chunks, logs); Qdrant stores one vector per chunk keyed by chunk id. Keeping the two stores in sync is the ingestion service's job. Trade-off accepted: two systems instead of one, in exchange for hands-on experience with a real vector database. The `VectorStore` abstraction keeps the swap back cheap.
