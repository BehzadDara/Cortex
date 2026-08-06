from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Form,
    HTTPException,
    UploadFile,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import (
    get_embedding_provider,
    get_session,
    get_vector_store,
    get_vision_provider,
)
from app.jobs import create_job, run_crawl, run_repository
from app.models import Collection, Document
from app.rag.embeddings import EmbeddingProvider
from app.rag.ingestion import DuplicateDocumentError, ingest_document
from app.rag.parsers import build_parsers, parser_for, supported_suffixes
from app.rag.vector_store import VectorStore
from app.rag.vision import VisionProvider
from app.schemas import (
    CrawlRequest,
    DocumentResponse,
    JobResponse,
    RepositoryRequest,
    to_job_response,
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
    vision: VisionProvider = Depends(get_vision_provider),
) -> DocumentResponse:
    parsers = build_parsers(vision)
    parser = parser_for(file.filename, parsers)
    if parser is None:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type. Supported: {supported_suffixes(parsers)}",
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


def ensure_collection_exists(session: Session, collection_id: int | None) -> None:
    if collection_id is not None and session.get(Collection, collection_id) is None:
        raise HTTPException(status_code=404, detail="Collection not found")


@router.post("/url", response_model=JobResponse, status_code=202)
def index_website(
    request: CrawlRequest,
    background: BackgroundTasks,
    session: Session = Depends(get_session),
) -> JobResponse:
    ensure_collection_exists(session, request.collection_id)
    job = create_job("website")
    background.add_task(
        run_crawl, job.id, request.url, request.max_pages, request.collection_id
    )
    return to_job_response(job)


@router.post("/repository", response_model=JobResponse, status_code=202)
def index_repository(
    request: RepositoryRequest,
    background: BackgroundTasks,
    session: Session = Depends(get_session),
) -> JobResponse:
    ensure_collection_exists(session, request.collection_id)
    job = create_job("repository")
    background.add_task(run_repository, job.id, request.url, request.collection_id)
    return to_job_response(job)


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
