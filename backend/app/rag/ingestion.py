import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Chunk, Document, Image
from app.rag.chunking import split_for
from app.rag.embeddings import EmbeddingProvider
from app.rag.file_store import FileStore
from app.rag.images import ExtractedImage, deduplicate_images
from app.rag.prompts import CAPTION_PROMPT
from app.rag.vector_store import VectorStore
from app.rag.vision import VisionProvider


class DuplicateDocumentError(Exception):
    def __init__(self, filename: str) -> None:
        super().__init__(f"Identical content already ingested as {filename}")


def document_payload(document: Document) -> dict:
    payload = {"document_id": document.id}
    if document.collection_id is not None:
        payload["collection_id"] = document.collection_id
    return payload


def ingest_document(
    session: Session,
    filename: str,
    text: str,
    embeddings: EmbeddingProvider,
    vector_store: VectorStore,
    collection_id: int | None = None,
    images: list[ExtractedImage] | None = None,
    vision: VisionProvider | None = None,
    image_store: FileStore | None = None,
    image_vector_store: VectorStore | None = None,
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
        for piece in split_for(filename, text)
    ]
    session.add(document)
    session.flush()

    vectors = embeddings.embed_documents([chunk.content for chunk in document.chunks])
    vector_store.add(
        [chunk.id for chunk in document.chunks],
        vectors,
        [document_payload(document)] * len(document.chunks),
    )

    if images and vision and image_store and image_vector_store:
        ingest_images(
            session, document, images, vision, image_store, embeddings,
            image_vector_store,
        )

    session.commit()
    return document


def describe_image(vision: VisionProvider, image: ExtractedImage) -> str | None:
    try:
        return vision.describe(image.data, CAPTION_PROMPT)
    except Exception:
        return None


def ingest_images(
    session: Session,
    document: Document,
    images: list[ExtractedImage],
    vision: VisionProvider,
    image_store: FileStore,
    embeddings: EmbeddingProvider,
    image_vector_store: VectorStore,
) -> None:
    kept = deduplicate_images(images)[: settings.max_images_per_document]
    records = []
    for position, extracted in enumerate(kept):
        caption = describe_image(vision, extracted)
        if not caption:
            continue
        records.append(
            Image(
                document_id=document.id,
                filename=image_store.save(extracted.data, extracted.extension),
                caption=caption,
                source_url=extracted.source_url,
                position=position,
            )
        )
    if not records:
        return
    session.add_all(records)
    session.flush()

    vectors = embeddings.embed_documents([record.caption for record in records])
    image_vector_store.add(
        [record.id for record in records],
        vectors,
        [document_payload(document)] * len(records),
    )
