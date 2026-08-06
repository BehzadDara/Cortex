import httpx
from fastapi import FastAPI
from sqlalchemy import text

from app.config import settings
from app.database import engine

app = FastAPI(title="Cortex")


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
