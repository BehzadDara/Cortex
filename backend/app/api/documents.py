from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_embedding_provider, get_session, get_vector_store
from app.models import Collection, Document
from app.rag.crawler import crawl
from app.rag.embeddings import EmbeddingProvider
from app.rag.ingestion import DuplicateDocumentError, ingest_document
from app.rag.parsers import parser_for, supported_suffixes
from app.rag.repository import collect_files
from app.rag.vector_store import VectorStore
from app.schemas import (
    BatchIngestResponse,
    CrawlRequest,
    DocumentResponse,
    RepositoryRequest,
)

router = APIRouter(prefix="/documents", tags=["documents"])


def to_response(document: Document) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        chunk_count=len(document.chunks),
        collection_id=document.collection_id,
        created_at=document.created_at,
    )


@router.post("", response_model=DocumentResponse)
def upload_document(
    file: UploadFile,
    collection_id: int | None = Form(None),
    session: Session = Depends(get_session),
    embeddings: EmbeddingProvider = Depends(get_embedding_provider),
    vector_store: VectorStore = Depends(get_vector_store),
) -> DocumentResponse:
    parser = parser_for(file.filename)
    if parser is None:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type. Supported: {supported_suffixes()}",
        )

    ensure_collection_exists(session, collection_id)

    try:
        text = parser.parse(file.file.read())
    except Exception:
        raise HTTPException(status_code=422, detail="Could not parse file")

    try:
        document = ingest_document(
            session, file.filename, text, embeddings, vector_store, collection_id
        )
    except DuplicateDocumentError as error:
        raise HTTPException(status_code=409, detail=str(error))

    return to_response(document)


def ingest_batch(
    session: Session,
    items: list[tuple[str, str]],
    embeddings: EmbeddingProvider,
    vector_store: VectorStore,
    collection_id: int | None,
) -> BatchIngestResponse:
    ingested = []
    skipped = 0
    for name, text in items:
        try:
            document = ingest_document(
                session, name, text, embeddings, vector_store, collection_id
            )
            ingested.append(to_response(document))
        except DuplicateDocumentError:
            skipped += 1
    return BatchIngestResponse(ingested=ingested, skipped=skipped)


def ensure_collection_exists(session: Session, collection_id: int | None) -> None:
    if collection_id is not None and session.get(Collection, collection_id) is None:
        raise HTTPException(status_code=404, detail="Collection not found")


@router.post("/url", response_model=BatchIngestResponse)
def index_website(
    request: CrawlRequest,
    session: Session = Depends(get_session),
    embeddings: EmbeddingProvider = Depends(get_embedding_provider),
    vector_store: VectorStore = Depends(get_vector_store),
) -> BatchIngestResponse:
    ensure_collection_exists(session, request.collection_id)

    pages = crawl(request.url, request.max_pages)
    if not pages:
        raise HTTPException(status_code=422, detail="No pages could be crawled")

    return ingest_batch(
        session,
        [(page.url, page.text) for page in pages],
        embeddings,
        vector_store,
        request.collection_id,
    )


@router.post("/repository", response_model=BatchIngestResponse)
def index_repository(
    request: RepositoryRequest,
    session: Session = Depends(get_session),
    embeddings: EmbeddingProvider = Depends(get_embedding_provider),
    vector_store: VectorStore = Depends(get_vector_store),
) -> BatchIngestResponse:
    ensure_collection_exists(session, request.collection_id)

    try:
        files = collect_files(request.url)
    except Exception:
        raise HTTPException(status_code=422, detail="Could not clone repository")
    if not files:
        raise HTTPException(status_code=422, detail="No indexable files found")

    return ingest_batch(
        session,
        [(file.path, file.text) for file in files],
        embeddings,
        vector_store,
        request.collection_id,
    )


@router.get("", response_model=list[DocumentResponse])
def list_documents(session: Session = Depends(get_session)) -> list[DocumentResponse]:
    documents = session.scalars(select(Document)).all()
    return [to_response(document) for document in documents]


@router.delete("/{document_id}", status_code=204)
def delete_document(
    document_id: int,
    session: Session = Depends(get_session),
    vector_store: VectorStore = Depends(get_vector_store),
) -> None:
    document = session.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    vector_store.remove([chunk.id for chunk in document.chunks])
    session.delete(document)
    session.commit()
