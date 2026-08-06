import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Chunk, Document
from app.rag.chunking import split_text
from app.rag.embeddings import EmbeddingProvider
from app.rag.vector_store import VectorStore


class DuplicateDocumentError(Exception):
    def __init__(self, filename: str) -> None:
        super().__init__(f"Identical content already ingested as {filename}")


def ingest_document(
    session: Session,
    filename: str,
    text: str,
    embeddings: EmbeddingProvider,
    vector_store: VectorStore,
    collection_id: int | None = None,
) -> Document:
    content_hash = hashlib.sha256(text.encode()).hexdigest()
    duplicate = session.scalar(
        select(Document).where(Document.content_hash == content_hash)
    )
    if duplicate:
        raise DuplicateDocumentError(duplicate.filename)

    document = Document(
        filename=filename, content_hash=content_hash, collection_id=collection_id
    )
    document.chunks = [
        Chunk(content=piece.content, position=piece.position)
        for piece in split_text(text, settings.chunk_size, settings.chunk_overlap)
    ]
    session.add(document)
    session.flush()

    payload = {"document_id": document.id}
    if collection_id is not None:
        payload["collection_id"] = collection_id

    vectors = embeddings.embed_documents([chunk.content for chunk in document.chunks])
    vector_store.add(
        [chunk.id for chunk in document.chunks],
        vectors,
        [payload] * len(document.chunks),
    )

    session.commit()
    return document
