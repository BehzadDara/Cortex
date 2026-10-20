from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audio_overviews import run_audio_overview
from app.config import settings
from app.dependencies import get_overview_audio_store, get_session
from app.models import AudioOverview, Collection
from app.rag.file_store import FileStore
from app.schemas import (
    AudioOverviewCreate,
    AudioOverviewDetail,
    AudioOverviewSummary,
)

router = APIRouter(prefix="/audio-overviews", tags=["audio overviews"])


def summary_fields(overview: AudioOverview) -> dict:
    return {
        "id": overview.id,
        "collection_id": overview.collection_id,
        "collection_name": overview.collection.name if overview.collection else None,
        "length": overview.length,
        "focus": overview.focus,
        "title": overview.title,
        "status": overview.status,
        "stage": overview.stage,
        "progress": overview.progress,
        "detail": overview.detail,
        "audio_filename": overview.audio_filename,
        "duration_ms": overview.duration_ms,
        "created_at": overview.created_at,
        "finished_at": overview.finished_at,
    }


def to_summary(overview: AudioOverview) -> AudioOverviewSummary:
    return AudioOverviewSummary(**summary_fields(overview))


def to_detail(overview: AudioOverview) -> AudioOverviewDetail:
    return AudioOverviewDetail(
        **summary_fields(overview),
        hosts=list(settings.overview_host_voices),
        segments=overview.segments or [],
        lines=overview.lines or [],
        sources=overview.sources or [],
    )


def find_overview(session: Session, overview_id: int) -> AudioOverview:
    overview = session.get(AudioOverview, overview_id)
    if overview is None:
        raise HTTPException(status_code=404, detail="Audio overview not found")
    return overview


@router.post("", response_model=AudioOverviewDetail, status_code=202)
def create_overview(
    request: AudioOverviewCreate,
    background: BackgroundTasks,
    session: Session = Depends(get_session),
) -> AudioOverviewDetail:
    collection = session.get(Collection, request.collection_id)
    if collection is None:
        raise HTTPException(status_code=404, detail="Collection not found")
    if not collection.documents:
        raise HTTPException(
            status_code=400, detail="Add documents to this collection first."
        )
    focus = " ".join((request.focus or "").split()) or None
    overview = AudioOverview(
        collection_id=collection.id, length=request.length, focus=focus
    )
    session.add(overview)
    session.commit()
    background.add_task(run_audio_overview, overview.id)
    return to_detail(overview)


@router.get("", response_model=list[AudioOverviewSummary])
def list_overviews(session: Session = Depends(get_session)) -> list[AudioOverviewSummary]:
    overviews = session.scalars(
        select(AudioOverview).order_by(AudioOverview.created_at.desc())
    )
    return [to_summary(overview) for overview in overviews]


@router.get("/{overview_id}", response_model=AudioOverviewDetail)
def get_overview(
    overview_id: int, session: Session = Depends(get_session)
) -> AudioOverviewDetail:
    return to_detail(find_overview(session, overview_id))


@router.delete("/{overview_id}", status_code=204)
def delete_overview(
    overview_id: int,
    session: Session = Depends(get_session),
    audio_store: FileStore = Depends(get_overview_audio_store),
) -> None:
    overview = find_overview(session, overview_id)
    if overview.audio_filename:
        audio_store.delete(overview.audio_filename)
    session.delete(overview)
    session.commit()
