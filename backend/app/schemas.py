from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CollectionCreate(BaseModel):
    name: str


class CollectionResponse(BaseModel):
    id: int
    name: str
    document_count: int
    created_at: datetime


class DocumentResponse(BaseModel):
    id: int
    filename: str
    chunk_count: int
    collection_id: int | None
    created_at: datetime


class CrawlRequest(BaseModel):
    url: str
    collection_id: int | None = None
    max_pages: int = Field(default=5, ge=1, le=20)


class RepositoryRequest(BaseModel):
    url: str
    collection_id: int | None = None


class JobResponse(BaseModel):
    id: int
    kind: str
    status: str
    detail: str | None
    created_at: datetime
    finished_at: datetime | None


def to_job_response(job) -> JobResponse:
    return JobResponse(
        id=job.id,
        kind=job.kind,
        status=job.status,
        detail=job.detail,
        created_at=job.created_at,
        finished_at=job.finished_at,
    )


class AskRequest(BaseModel):
    question: str
    conversation_id: int | None = None
    timezone: str | None = None


class ResumeRequest(BaseModel):
    thread: str
    conversation_id: int
    approved: bool


class ContinueRequest(BaseModel):
    conversation_id: int


class ImageAskResponse(BaseModel):
    conversation_id: int
    answer: str


class StatsResponse(BaseModel):
    documents: int
    chunks: int
    collections: int
    conversations: int
    prompts: int
    likes: int
    dislikes: int
    average_latency_ms: float | None
    total_prompt_tokens: int
    total_response_tokens: int


class PromptLogResponse(BaseModel):
    id: int
    question: str
    response: str
    model: str
    latency_ms: int
    prompt_tokens: int | None
    response_tokens: int | None
    created_at: datetime


class ToolStep(BaseModel):
    name: str
    arguments: dict
    result: str | None = None


class SourceRef(BaseModel):
    id: int
    filename: str
    content: str
    url: str | None = None


class WidgetPayload(BaseModel):
    kind: str
    data: dict


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    steps: list[ToolStep] | None = None
    sources: list[SourceRef] | None = None
    widgets: list[WidgetPayload] | None = None
    feedback: Literal["like", "dislike"] | None = None
    elapsed_ms: int | None = None
    prompt_tokens: int | None = None
    response_tokens: int | None = None


class FeedbackRequest(BaseModel):
    value: Literal["like", "dislike"] | None


class FeedbackResponse(BaseModel):
    id: int
    feedback: Literal["like", "dislike"] | None


class ConversationSummary(BaseModel):
    id: int
    title: str
    message_count: int
    created_at: datetime


class ConversationRename(BaseModel):
    title: str = Field(min_length=1, max_length=80)


class ConversationResponse(BaseModel):
    id: int
    summary: str | None
    active_thread: str | None
    branched_from_id: int | None
    branched_from_title: str | None
    branched_count: int | None
    messages: list[MessageResponse]
