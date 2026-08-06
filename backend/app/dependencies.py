from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.rag.embeddings import EmbeddingProvider, OllamaEmbeddingProvider
from app.rag.llm import LLMProvider, OllamaLLMProvider
from app.rag.vector_store import QdrantVectorStore, VectorStore


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    return OllamaEmbeddingProvider()


@lru_cache
def get_llm_provider() -> LLMProvider:
    return OllamaLLMProvider()


@lru_cache
def get_vector_store() -> VectorStore:
    return QdrantVectorStore()
