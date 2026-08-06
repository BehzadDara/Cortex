from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_embedding_provider, get_session, get_vector_store
from app.models import Document
from app.rag.embeddings import EmbeddingProvider
from app.rag.ingestion import ingest_document
from app.rag.vector_store import VectorStore
from app.schemas import DocumentResponse

router = APIRouter(prefix="/documents", tags=["documents"])

SUPPORTED_SUFFIXES = {".txt", ".md"}


def to_response(document: Document) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        chunk_count=len(document.chunks),
        created_at=document.created_at,
    )


@router.post("", response_model=DocumentResponse)
def upload_document(
    file: UploadFile,
    session: Session = Depends(get_session),
    embeddings: EmbeddingProvider = Depends(get_embedding_provider),
    vector_store: VectorStore = Depends(get_vector_store),
) -> DocumentResponse:
    suffix = Path(file.filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {suffix}")

    text = file.file.read().decode("utf-8")
    document = ingest_document(session, file.filename, text, embeddings, vector_store)
    return to_response(document)


@router.get("", response_model=list[DocumentResponse])
def list_documents(session: Session = Depends(get_session)) -> list[DocumentResponse]:
    documents = session.scalars(select(Document)).all()
    return [to_response(document) for document in documents]
