from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api import (
    assistant,
    collections,
    conversations,
    documents,
    jobs,
    messages,
    stats,
    vision,
    voice,
)
from app.checkpoints import warm_checkpointer
from app.config import settings
from app.database import engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    warm_checkpointer()
    yield


images_dir = Path(settings.image_dir)
images_dir.mkdir(parents=True, exist_ok=True)
knowledge_images_dir = Path(settings.knowledge_image_dir)
knowledge_images_dir.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Cortex", lifespan=lifespan)
app.mount("/images", StaticFiles(directory=images_dir), name="images")
app.mount(
    "/knowledge-images",
    StaticFiles(directory=knowledge_images_dir),
    name="knowledge_images",
)
app.include_router(collections.router)
app.include_router(documents.router)
app.include_router(conversations.router)
app.include_router(messages.router)
app.include_router(assistant.router)
app.include_router(vision.router)
app.include_router(voice.router)
app.include_router(stats.router)
app.include_router(jobs.router)


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
