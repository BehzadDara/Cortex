---
description: Start the full Cortex stack (Docker containers, n8n, Ollama, backend, frontend) and verify everything is up
---

Start the full Cortex stack in this order. Do not skip the verification at the end.

## 1. Docker containers (Postgres + Qdrant + n8n)

```bash
docker compose -f /Users/azki/Desktop/Projects/Mine/Cortex/docker/docker-compose.yml up -d
```

If this fails because the Docker daemon is not running, run `open -a Docker`, then poll `docker info` every 3 seconds until it responds (up to 60s), and retry the compose command.

## 2. Ollama

Check first: `curl -s -m 3 http://localhost:11434/api/version`. If it responds, Ollama is already running — skip. Otherwise:

```bash
brew services start ollama
```

## 3. Stop stale servers

```bash
pkill -f "uvicorn app.main:app"; pkill -f "Cortex/frontend"; sleep 2
```

## 4. Start backend and frontend as background tasks

The agent's shell kills every process a command started once that command returns — `&`, `( … &)`, `nohup` and `disown` all die with it. Each server must therefore be launched as **its own long-running background shell task**, one per server:

- Cursor: a Shell call with `block_until_ms: 0`
- Claude Code: a Bash call with `run_in_background: true`

Never chain them into one call, and never append `&`.

Backend (FastAPI on port 8100):

```bash
cd /Users/azki/Desktop/Projects/Mine/Cortex/backend && .venv/bin/uvicorn app.main:app --port 8100 --reload 2>&1 | tee /tmp/cortex-backend.log
```

Frontend (Vite on port 5100):

```bash
cd /Users/azki/Desktop/Projects/Mine/Cortex/frontend && npm run dev 2>&1 | tee /tmp/cortex-frontend.log
```

## 5. Verify — required

Run the checks in a **separate** foreground call after both tasks have started, polling up to ~30s:

- `curl -s http://localhost:8100/health` must return `{"database":"up","qdrant":"up","ollama":"up"}` — all three up.
- `curl -s -m 3 http://localhost:5678/healthz` must return `{"status":"ok"}`. n8n can take longer than Postgres and Qdrant; keep polling it with the other checks.
- `curl -s http://localhost:5100` must return HTML containing `<title>Cortex</title>`.

Then confirm the servers outlived the commands that started them — wait 5 seconds and check both ports are still listening:

```bash
sleep 5; lsof -nP -iTCP:8100 -iTCP:5100 -sTCP:LISTEN
```

Both 8100 (Python) and 5100 (node) must appear. If either is missing, the server was started the wrong way — go back to step 4.

If any check fails, read the relevant log (`/tmp/cortex-backend.log`, `/tmp/cortex-frontend.log`, `docker ps`) and fix the problem before reporting.

Finish by reporting the status of each component, the app URL http://localhost:5100, and n8n at http://localhost:5678. Vite listens on IPv6 loopback only, so `localhost` works and `127.0.0.1` does not.
