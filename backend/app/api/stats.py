from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.dependencies import get_session
from app.models import Chunk, Collection, Conversation, Document, PromptLog
from app.schemas import PromptLogResponse, StatsResponse

router = APIRouter(tags=["stats"])


@router.get("/stats", response_model=StatsResponse)
def stats(session: Session = Depends(get_session)) -> StatsResponse:
    return StatsResponse(
        documents=session.scalar(select(func.count(Document.id))),
        chunks=session.scalar(select(func.count(Chunk.id))),
        collections=session.scalar(select(func.count(Collection.id))),
        conversations=session.scalar(select(func.count(Conversation.id))),
        prompts=session.scalar(select(func.count(PromptLog.id))),
        average_latency_ms=session.scalar(select(func.avg(PromptLog.latency_ms))),
        total_prompt_tokens=session.scalar(
            select(func.coalesce(func.sum(PromptLog.prompt_tokens), 0))
        ),
        total_response_tokens=session.scalar(
            select(func.coalesce(func.sum(PromptLog.response_tokens), 0))
        ),
    )


@router.get("/logs", response_model=list[PromptLogResponse])
def logs(
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
) -> list[PromptLogResponse]:
    entries = session.scalars(
        select(PromptLog).order_by(PromptLog.id.desc()).limit(limit)
    ).all()
    return [
        PromptLogResponse(
            id=entry.id,
            question=entry.question,
            response=entry.response,
            model=entry.model,
            latency_ms=entry.latency_ms,
            prompt_tokens=entry.prompt_tokens,
            response_tokens=entry.response_tokens,
            created_at=entry.created_at,
        )
        for entry in entries
    ]
