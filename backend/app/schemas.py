from datetime import datetime

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


class BatchIngestResponse(BaseModel):
    ingested: list[DocumentResponse]
    skipped: int


class AskRequest(BaseModel):
    question: str
    collection_id: int | None = None
