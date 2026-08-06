from typing import Protocol

import httpx

from app.config import settings


class EmbeddingProvider(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class OllamaEmbeddingProvider:
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed([f"search_document: {text}" for text in texts])

    def embed_query(self, text: str) -> list[float]:
        return self._embed([f"search_query: {text}"])[0]

    def _embed(self, texts: list[str]) -> list[list[float]]:
        response = httpx.post(
            f"{settings.ollama_url}/api/embed",
            json={"model": settings.embedding_model, "input": texts},
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["embeddings"]
