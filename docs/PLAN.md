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
- [x] **16. LangGraph orchestration** — Agent rebuilt as a `StateGraph` with parallel retrieval fan-out, measured against the hand-rolled pipeline, then Chat + Agent merged into one streaming `/assistant` (model ⇄ tools cycle with live tool-step events). Postgres checkpointing makes runs resumable; `interrupt()` adds human-in-the-loop approval for web searches. Finally Ask folded in too: an always-first `retrieve` node seeds the loop with grounded context, leaving a single conversation surface; the chat collection filter was removed with it.
- [x] **17. Rich answers** — Mermaid diagrams rendered to downloadable SVG. Tools with visual payloads render as live widget cards, persisted on the message for replay: world clock, weather (Open-Meteo), 24h crypto chart (CoinGecko), plus Cortex-internal knowledge-base stats and 7-day usage. The router judges follow-ups with the previous question attached — 100% on the routing set, now 38 questions.
- [x] **18. Answer feedback** — Like/dislike on every assistant answer: one vote per message, editable and clearable (last state wins), persisted and replayed with the chat; totals on the dashboard. The run's persisted message id now streams back as a `saved` event before `done`.
- [x] **19. Branching** — Any assistant answer can branch into a new chat: a deep copy of the conversation up to that answer (messages, traces, sources, widgets, summary), opened immediately. The branch shows a divider at the copy point — "Branched from ⟨title⟩", clickable back to the source; deleting the source detaches the link without touching the branch.
- [x] **20. Image generation** — A `generate_image` tool behind an `ImageGenerator` abstraction; the image lands on disk served at `/images`, and the answer shows it as an image card widget with a download button, persisted and replayed like the others. Built first on Ollama's experimental image API (`x/z-image-turbo` locally), which proved too heavy beside the chat models on 24 GB — replaced by the free keyless Pollinations API (~2 s per image) and the local implementation was deleted, git history keeping the escape hatch. Draw-requests route straight to the model; the routing set grew to 42 questions — 100%.
- [x] **21. Knowledge images** — Pictures survive ingestion: embedded PDF/DOCX images, crawled pages' pictures, and uploaded image files are validated, deduplicated, captioned by the vision model, stored on disk behind a new `FileStore` abstraction, and indexed by caption in a second Qdrant collection. Every document search also searches captions and attaches the relevance-gated survivors as an `image_gallery` widget card; approved web searches do the same with photos of their query (titles reranked, downloads persisted so replays never break), and an approval-gated `web_image_search` tool (ddgs images behind `ImageSearchProvider`) covers explicit picture requests. Deleting a document cleans up its image rows, vectors, and files.
- [x] **22. Video player** — An approval-gated `web_video_search` tool behind a `VideoSearchProvider` abstraction (ddgs videos, no key): results are filtered to YouTube, normalized to YouTube embed URLs, and rendered as a `video_player` widget — a click-to-load player (thumbnail, duration badge, channel, YouTube link) with the remaining videos as compact rows that swap into the player and autoplay. Nothing plays until clicked, and nothing is downloaded: a video that later dies degrades to its thumbnail and YouTube link. The routing set grew to 46 questions — 100%.
- [x] **23. Voice input** — A `SpeechToText` abstraction (Whisper large-v3-turbo via mlx-whisper, loaded in-process like the reranker), a `/transcribe` endpoint, and a mic button in the chat composer: the browser records, downmixes to 16 kHz mono WAV, and the transcript auto-sends through the normal `/assistant` flow — nothing downstream changes, and audio never leaves the machine.
- [x] **24. Voice output** — A `TextToSpeech` abstraction (Kokoro via kokoro-onnx, weights in `backend/voice_models/`), a `/speak` endpoint that strips markdown and citation markers before rendering the answer as WAV, and a read-aloud button on every saved assistant answer.
- [x] **25. Response variants** — Conversations became message trees: `parent_id` makes an answer's siblings its alternatives, and an `active_child_id` per message (plus `active_root_id` on the conversation) records which one is on the visible path. Regenerate adds an assistant sibling, editing a question adds a user sibling with its own answer, and `‹ n/m ›` arrows step between them — each variant keeping its own continuation, trace, sources, widgets, and vote. Conversation summaries moved from the conversation row onto the messages so they stay correct per path; branch now copies the path, which deleted its old summary special case. Images asked about in chat are persisted too: `/ask-image` uploads go through a `chat_images` `FileStore` and are recorded in a new `attachments` column, replacing the filename marker that used to be spliced into the message text.

## Principles

- Frontend (React + Vite) lives in `frontend/`: Vite dev server proxies `/api` to the backend.
- Redis, MinIO, and any other infrastructure are added only when a step needs them.
- Decisions and lessons are recorded in `docs/DECISIONS.md` as they happen.

## Future ideas

Slack/Discord integration, browser extension, semantic caching, citation highlighting, local file watcher, incremental indexing.
