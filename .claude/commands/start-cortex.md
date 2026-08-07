---
description: Start the full Cortex stack (Docker containers, Ollama, backend, frontend) and verify everything is up
---

Start the full Cortex stack in this order. Do not skip the verification at the end.

## 1. Docker containers (Postgres + Qdrant)

```bash
docker compose -f /Users/azki/Desktop/Projects/Mine/Cortex/docker/docker-compose.yml up -d
```

If this fails because the Docker daemon is not running, run `open -a Docker`, then poll `docker info` every 3 seconds until it responds (up to 60s), and retry the compose command.

## 2. Ollama

Check first: `curl -s -m 3 http://localhost:11434/api/version`. If it responds, Ollama is already running — skip. Otherwise:

```bash
brew services start ollama
```

## 3. Backend (FastAPI on port 8100)

Kill any stale process first, then start fresh. Always use the absolute venv path — never a relative one:

```bash
pkill -f "uvicorn app.main:app"; sleep 1
(/Users/azki/Desktop/Projects/Mine/Cortex/backend/.venv/bin/uvicorn app.main:app --app-dir /Users/azki/Desktop/Projects/Mine/Cortex/backend --port 8100 --reload >/tmp/cortex-backend.log 2>&1 &)
```

## 4. Frontend (Vite on port 5100)

```bash
pkill -f "Cortex/frontend"; sleep 1
cd /Users/azki/Desktop/Projects/Mine/Cortex/frontend && (npm run dev >/tmp/cortex-frontend.log 2>&1 &)
```

## 5. Verify — required

Poll until healthy (up to ~30s):

- `curl -s http://localhost:8100/health` must return `{"database":"up","qdrant":"up","ollama":"up"}` — all three up.
- `curl -s http://localhost:5100` must return HTML containing `<title>Cortex</title>`.

If any check fails, read the relevant log (`/tmp/cortex-backend.log`, `/tmp/cortex-frontend.log`, `docker ps`) and fix the problem before reporting.

Finish by reporting the status of each component and the URL http://localhost:5100.
