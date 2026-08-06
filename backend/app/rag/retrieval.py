from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Chunk, Document
from app.rag.embeddings import EmbeddingProvider
from app.rag.vector_store import VectorStore

RRF_K = 60


def keyword_search(
    session: Session, question: str, limit: int, collection_id: int | None = None
) -> list[int]:
    ts_vector = func.to_tsvector("english", Chunk.content)
    ts_query = func.plainto_tsquery("english", question)
    query = select(Chunk.id).where(ts_vector.op("@@")(ts_query))
    if collection_id:
        query = query.join(Document).where(Document.collection_id == collection_id)
    query = query.order_by(func.ts_rank(ts_vector, ts_query).desc()).limit(limit)
    return list(session.scalars(query))


def reciprocal_rank_fusion(rankings: list[list[int]]) -> list[int]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking):
            scores[chunk_id] = scores.get(chunk_id, 0) + 1 / (RRF_K + rank + 1)
    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return [chunk_id for chunk_id, _ in ordered]


def retrieve_chunks(
    session: Session,
    question: str,
    limit: int,
    embeddings: EmbeddingProvider,
    vector_store: VectorStore,
    collection_id: int | None = None,
) -> list[Chunk]:
    query_vector = embeddings.embed_query(question)
    filters = {"collection_id": collection_id} if collection_id else None
    vector_ids = [
        result.chunk_id for result in vector_store.search(query_vector, limit, filters)
    ]

    if settings.hybrid_search:
        keyword_ids = keyword_search(session, question, limit, collection_id)
        chunk_ids = reciprocal_rank_fusion([vector_ids, keyword_ids])[:limit]
    else:
        chunk_ids = vector_ids

    chunks = session.scalars(select(Chunk).where(Chunk.id.in_(chunk_ids))).all()
    rank = {chunk_id: index for index, chunk_id in enumerate(chunk_ids)}
    return sorted(chunks, key=lambda chunk: rank[chunk.id])
