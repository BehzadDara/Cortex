# Decisions

A running log of technical decisions and lessons, newest first.

## 2026-08-09 — Token counts restored, accumulated in graph state

When Ask folded into the assistant, token counts were "dropped for now": the old `/ask` path read Ollama's `prompt_eval_count`/`eval_count` from `stream()`, but the assistant answers through `chat_stream`, which discarded them — the dashboard token tiles have silently read 0 since. Restored end to end: `chat_stream` captures the counts from the final chunk into `ChatReply`, and the model node adds them to two reducer fields in graph state (`operator.add`), which sums them across tool-loop rounds and — because state checkpoints to Postgres — carries them through approval interrupts and crash recovery with no extra bookkeeping. A completed run emits a `usage` SSE event before `done`; the totals persist to `prompt_logs` and onto the assistant message, so reopened chats show usage the same way they replay steps and citations, rendered as a muted line under the answer. Verified on a run that paused for web-search approval and resumed: both model rounds summed correctly across the two HTTP requests. Two honest numbers to know when reading it: response tokens include qwen3's discarded thinking (the visible answer is a fraction of the compute), and the counts cover the answering model only — route, title, and summary calls are excluded as bookkeeping. Lesson: usage belongs in run state, not request scope — the same argument that put the citation registry there.

## 2026-08-08 — Run state must not outlive its conversation

A chat paused on web-search approval locked the composer in every other chat, including new ones. Root cause: `busy` and the awaiting-approval flag are view-level state shared by all conversations, and the route-change handler reset messages but not them — the lock leaked across chats. The fix leans on the crash-recovery design instead of adding state machinery: switching conversations now aborts the in-flight stream (AbortController through every fetch) and clears the run flags. An aborted stream is indistinguishable from a crash on the server — the run stays checkpointed under its `active_thread`, so returning to that chat auto-continues it, and a pending approval card simply re-emerges from the re-raised interrupt. This also closed the nastier sibling bug: an uncancelled stream's handlers kept writing to "the last message" after a switch, which would have appended chat A's tokens into chat B's bubble. Two guards matter: the route effect only aborts when the route actually differs from the current conversation (otherwise adopting a newly created chat would abort its own first stream), and each stream's cleanup checks its own abort signal so a dying stream can't flip `busy` under the next one.

## 2026-08-08 — A measured router decides when to skip document search

"Search the web: what's the Bitcoin price?" still ran the seeded document search first — harmless (the relevance gate emptied it) but wasteful and noisy in the trace. Fix: a `route` node at the graph entry asks gemma3:4b one question — does this message need the user's documents? — and a conditional edge either runs the seeded `retrieve` or jumps straight to the model. Router cost ~460 ms, roughly what the skipped search costs, so latency nets out; the win is an honest trace. Per the house rule, the router was measured before being trusted: a 24-question routing golden set (`evals/routing.py`). First prompt scored 79% with two errors in the dangerous direction (document questions routed away from grounding — a false "no" silently un-grounds an answer, while a false "yes" just wastes a search). Rewriting the rules-only prompt into a few-shot prompt with eight labeled examples moved it to 96% with zero dangerous misses; the one remaining error routes "hi" to documents, the harmless direction. Lesson twice over: small models classify far better from examples than from rules, and an asymmetric-cost decision needs its error directions reported separately — a single accuracy number would have hidden exactly the failures that matter.

## 2026-08-08 — Web results joined the citation registry

First real answer with a web claim exposed a hallucinated citation: "$63,709.78 USD [5]" where no source 5 existed — document chunks were numbered but web results were an unnumbered text blob, so the model invented a plausible-looking id (and the frontend, correctly, refused to render it as a chip). Fix: web results register in the same state-held sources registry as document chunks, with their URLs; the tool result the model reads shows `[n] title / url / snippet`, and the source card in the UI links out to the page. Retested: five numbered web sources, answer cited [2], chip resolves to the exact page the price came from. Lesson: a citation scheme must cover every evidence channel the model sees, or the model will improvise numbers for the uncovered one.

## 2026-08-08 — Citations and crash-proof streams

Two features cashed in infrastructure that already existed. **Citations:** chunk metadata stored since day one finally pays off — every retrieved passage gets a global number (`[1] coffee.md`), the model is instructed to cite passage numbers after claims, and the frontend turns `[n]` markers into clickable chips that expand the exact source chunk. The numbering registry lives in graph state (not request scope) deliberately: an approval interrupt splits one run across two HTTP requests, and a request-scoped counter would restart at [1] and mis-map every earlier citation. qwen3:4b followed the citation instruction on the first try once passages carried visible numbers. **Stream resume:** the Postgres checkpointer already made runs durable; now the conversation row tracks its `active_thread`, and if the browser dies mid-answer, reopening the chat calls `/assistant/continue` — a `snapshot` event replays the question, steps, and sources from the checkpoint, then the graph re-runs from the last completed node and streams the rest. The interrupted node re-executes from its start (tokens may differ between attempts; tools re-run), which is the documented LangGraph trade-off for exactly-once-per-node checkpointing. A run killed before its first checkpoint returns 409 and clears the thread — that exchange is simply lost, which is honest. Verified by killing a live run at 20s and continuing it: the snapshot carried two steps, re-execution renumbered sources consistently, and the final answer persisted with citations intact.

## 2026-08-08 — Ask folded into the assistant: one conversation surface

The last tab split fell: `/ask` (the fixed RAG pipeline) merged into `/assistant` via an always-first `retrieve` node — the retrieval funnel runs with the raw question before the model's first turn, streamed and persisted as an ordinary `search_documents` step. Simple questions keep Ask's behavior (guaranteed grounding, one model turn, streamed answer); complex ones escalate into the tool loop. First test exposed a prompt bug: the raw comparative phrasing "Compare how coffee and tea are prepared" scored below the relevance gate, and the model jumped straight to `web_search`. One system-prompt change — "split into sub-topics and search documents again *before anything else*" — and the same question produced two focused searches hitting coffee.md and tea.docx, no web. Query rewriting for follow-ups was deleted with `/ask`: if the seeded search misses, the model re-searches with history in view, which is the same repair without a dedicated LLM call. Prompt logging moved to the assistant (transcript of steps as the logged prompt; token counts dropped for now). The chat collection filter was removed as unused friction — collections remain a document-organization feature. The eval harness still measures the retrieval funnel and `build_answer_prompt` directly, so retrieval changes stay measurable even though no endpoint runs that exact pipeline anymore.

## 2026-08-08 — Durable agent state and human-in-the-loop approval

The assistant graph now checkpoints to Postgres (`langgraph-checkpoint-postgres`): state is saved after every node under a per-request `thread_id`, which makes the run pausable and resumable across HTTP requests. On top of that sits the first human-in-the-loop gate: before executing `web_search`, the tools node calls `interrupt()` — the graph parks itself in the database, the SSE stream emits an `approval` event with the thread id and ends. `POST /assistant/resume` with `Command(resume=approved)` re-enters the node, `interrupt()` returns the decision, and the run continues (declined searches feed "the user declined" back to the model as the tool result). Approvals are gathered before any tool executes so a resume never re-runs a side effect. Two lessons paid for in debugging: psycopg's pool must be opened explicitly (`open=False` + `pool.open(wait=True)`) — the deprecated implicit open hung silently; and the checkpointer must be initialized at app startup, because lazy setup inside a request self-deadlocks — `CREATE INDEX CONCURRENTLY` waits for every open transaction, including the request's own SQLAlchemy session. Checkpoint rows accumulate per request; cleanup is deferred until it matters. Also observed: qwen3 sometimes answers post-cutoff questions from stale training knowledge instead of searching — model judgment, unlike the old hardcoded fallback, can be wrong in both directions.

## 2026-08-08 — Chat and Agent merged into one streaming Assistant

The tool-calling Chat and the plan-based Agent solved the same problem with opposite control flow: model-driven versus code-driven. Both are now one `/assistant` endpoint — a two-node LangGraph cycle (`model ⇄ tools`) where the model orchestrates itself, streaming every step over SSE (`tool_call`, `tool_result`, `token`, `title`). The open question was whether a 4B model could carry the orchestration the hardcoded planner guaranteed. Measured: "Compare how coffee and tea are prepared" produced two focused `search_documents` calls in one turn, each hitting the right file; the World Cup question skipped documents and answered from one `web_search` — where the workflow agent had burned four web searches and 136s on the same question. The relevance gate moved into the `search_documents` tool itself, so "no relevant documents" becomes something the model sees and reacts to. Tool steps persist as JSONB on the assistant message, so reopening a chat replays the trace. Both old endpoints and the Phase-A workflow graph are deleted; prompting a capable loop replaced hardcoded decomposition.

## 2026-08-08 — Agent rebuilt on LangGraph, retrieval fan-out parallelized

The hand-rolled planner → retriever → reasoner pipeline was rewritten as a LangGraph `StateGraph`: a `plan` node, a `Send` fan-out that runs one `retrieve` node per search query in parallel, and a `reason` node that deduplicates and synthesizes. LangGraph orchestrates only the control flow — every node still calls our own `LLMProvider`, retrieval funnel, and `WebSearchProvider`; no langchain model wrappers entered the project. Head-to-head on the same questions, answers were equally correct and the graph was faster because retrieval fans out in parallel: coffee-vs-tea 55.9s → 48.4s, World Cup (web fallback) 136.3s → 118.5s. The sequential pipeline is deleted; its dedup moved after the fan-in, since parallel steps can no longer see each other's chunks mid-flight. Side observation: plan phrasing drives relevance-gate hits — "step-by-step coffee brewing methods" scored below the gate against coffee.md while "How coffee is prepared" cleared it, so identical questions can route to web or documents depending on how the 4B model words its plan.

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
