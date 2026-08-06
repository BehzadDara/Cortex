import httpx
from fastapi import Depends, FastAPI
from sqlalchemy import text

from app.api import (
    agent,
    ask,
    chat,
    collections,
    conversations,
    documents,
    jobs,
    stats,
    vision,
)
from app.config import settings
from app.database import engine
from app.security import require_api_key

app = FastAPI(title="Cortex")
secured = [Depends(require_api_key)]
app.include_router(collections.router, dependencies=secured)
app.include_router(documents.router, dependencies=secured)
app.include_router(conversations.router, dependencies=secured)
app.include_router(ask.router, dependencies=secured)
app.include_router(chat.router, dependencies=secured)
app.include_router(agent.router, dependencies=secured)
app.include_router(vision.router, dependencies=secured)
app.include_router(stats.router, dependencies=secured)
app.include_router(jobs.router, dependencies=secured)


def database_status() -> str:
    try:
        with engine.connect() as connection:
            connection.execute(text("select 1"))
        return "up"
    except Exception:
        return "down"


def qdrant_status() -> str:
    try:
        httpx.get(f"{settings.qdrant_url}/healthz").raise_for_status()
        return "up"
    except Exception:
        return "down"


def ollama_status() -> str:
    try:
        httpx.get(f"{settings.ollama_url}/api/tags").raise_for_status()
        return "up"
    except Exception:
        return "down"


@app.get("/health")
def health() -> dict:
    return {
        "database": database_status(),
        "qdrant": qdrant_status(),
        "ollama": ollama_status(),
    }
