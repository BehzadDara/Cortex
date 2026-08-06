# Decisions

A running log of technical decisions and lessons, newest first.

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
