from dataclasses import dataclass
from typing import Protocol

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointIdsList,
    PointStruct,
    VectorParams,
)

from app.config import settings


@dataclass
class SearchResult:
    chunk_id: int
    score: float


class VectorStore(Protocol):
    def add(
        self, chunk_ids: list[int], vectors: list[list[float]], payloads: list[dict]
    ) -> None: ...

    def search(
        self, vector: list[float], limit: int, filters: dict | None = None
    ) -> list[SearchResult]: ...

    def remove(self, chunk_ids: list[int]) -> None: ...


class QdrantVectorStore:
    def __init__(self) -> None:
        self.client = QdrantClient(url=settings.qdrant_url)
        self.ensure_collection()

    def ensure_collection(self) -> None:
        if not self.client.collection_exists(settings.qdrant_collection):
            self.client.create_collection(
                collection_name=settings.qdrant_collection,
                vectors_config=VectorParams(
                    size=settings.embedding_dimensions, distance=Distance.COSINE
                ),
            )

    def add(
        self, chunk_ids: list[int], vectors: list[list[float]], payloads: list[dict]
    ) -> None:
        points = [
            PointStruct(id=chunk_id, vector=vector, payload=payload)
            for chunk_id, vector, payload in zip(chunk_ids, vectors, payloads)
        ]
        self.client.upsert(collection_name=settings.qdrant_collection, points=points)

    def search(
        self, vector: list[float], limit: int, filters: dict | None = None
    ) -> list[SearchResult]:
        hits = self.client.query_points(
            collection_name=settings.qdrant_collection,
            query=vector,
            limit=limit,
            query_filter=self.to_filter(filters),
        ).points
        return [SearchResult(chunk_id=hit.id, score=hit.score) for hit in hits]

    def remove(self, chunk_ids: list[int]) -> None:
        self.client.delete(
            collection_name=settings.qdrant_collection,
            points_selector=PointIdsList(points=chunk_ids),
        )

    def to_filter(self, filters: dict | None) -> Filter | None:
        if not filters:
            return None
        return Filter(
            must=[
                FieldCondition(key=key, match=MatchValue(value=value))
                for key, value in filters.items()
            ]
        )
