from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.dependencies import get_embedding_provider, get_vector_store
from app.models import Job
from app.rag.crawler import crawl
from app.rag.ingestion import DuplicateDocumentError, ingest_document
from app.rag.repository import collect_files


def create_job(kind: str) -> Job:
    with SessionLocal() as session:
        job = Job(kind=kind)
        session.add(job)
        session.commit()
        session.refresh(job)
        return job


def ingest_many(
    session: Session, items: list[tuple[str, str]], collection_id: int | None
) -> str:
    embeddings = get_embedding_provider()
    vector_store = get_vector_store()
    ingested = 0
    skipped = 0
    for name, text in items:
        try:
            ingest_document(
                session, name, text, embeddings, vector_store, collection_id
            )
            ingested += 1
        except DuplicateDocumentError:
            skipped += 1
    return f"ingested {ingested}, skipped {skipped}"


def run_job(job_id: int, work: Callable[[Session], str]) -> None:
    with SessionLocal() as session:
        job = session.get(Job, job_id)
        job.status = "running"
        session.commit()
        try:
            job.detail = work(session)
            job.status = "done"
        except Exception as error:
            job.status = "failed"
            job.detail = str(error)
        job.finished_at = datetime.now(timezone.utc)
        session.commit()


def run_crawl(
    job_id: int, url: str, max_pages: int, collection_id: int | None
) -> None:
    run_job(
        job_id,
        lambda session: ingest_many(
            session,
            [(page.url, page.text) for page in crawl(url, max_pages)],
            collection_id,
        ),
    )


def run_repository(job_id: int, url: str, collection_id: int | None) -> None:
    run_job(
        job_id,
        lambda session: ingest_many(
            session,
            [(file.path, file.text) for file in collect_files(url)],
            collection_id,
        ),
    )
