from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Chunk
from app.rag.embeddings import EmbeddingProvider
from app.rag.vector_store import VectorStore


def retrieve_chunks(
    session: Session,
    question: str,
    limit: int,
    embeddings: EmbeddingProvider,
    vector_store: VectorStore,
) -> list[Chunk]:
    query_vector = embeddings.embed_query(question)
    results = vector_store.search(query_vector, limit)
    chunk_ids = [result.chunk_id for result in results]
    chunks = session.scalars(select(Chunk).where(Chunk.id.in_(chunk_ids))).all()
    rank = {chunk_id: index for index, chunk_id in enumerate(chunk_ids)}
    return sorted(chunks, key=lambda chunk: rank[chunk.id])
