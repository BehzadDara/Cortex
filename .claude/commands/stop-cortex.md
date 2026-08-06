---
description: Stop the full Cortex stack (frontend, backend, Docker containers, Ollama) and verify everything is down
---

Stop the full Cortex stack. Do not skip the verification at the end.

## 1. Frontend and backend processes

```bash
pkill -f "Cortex/frontend"
pkill -f "uvicorn app.main:app"
```

`pkill` exits 1 when nothing matched — that is fine, it means the process was already stopped.

## 2. Docker containers

Never use `-v` here — the volumes hold the database and vectors:

```bash
docker compose -f /Users/azki/Desktop/Projects/Mine/Cortex/docker/docker-compose.yml down
```

## 3. Ollama

```bash
brew services stop ollama
```

## 4. Verify — required

- `pgrep -f "uvicorn app.main:app"` must find nothing.
- `pgrep -f "Cortex/frontend"` must find nothing.
- `docker ps --format '{{.Names}}'` must show no `cortex-` containers.
- `curl -s -m 3 http://localhost:11434/api/version` must fail to connect.

If anything is still running, stop it and re-verify before reporting.

Finish by confirming each component is stopped, and note that the data (Postgres volume, Qdrant volume, downloaded models) is preserved.
