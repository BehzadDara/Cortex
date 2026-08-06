from sqlalchemy.orm import Session

from app.config import settings
from app.models import Chunk, Document
from app.rag.chunking import split_text
from app.rag.embeddings import EmbeddingProvider
from app.rag.vector_store import VectorStore


def ingest_document(
    session: Session,
    filename: str,
    text: str,
    embeddings: EmbeddingProvider,
    vector_store: VectorStore,
) -> Document:
    document = Document(filename=filename)
    document.chunks = [
        Chunk(content=piece.content, position=piece.position)
        for piece in split_text(text, settings.chunk_size, settings.chunk_overlap)
    ]
    session.add(document)
    session.flush()

    vectors = embeddings.embed_documents([chunk.content for chunk in document.chunks])
    vector_store.add([chunk.id for chunk in document.chunks], vectors)

    session.commit()
    return document
