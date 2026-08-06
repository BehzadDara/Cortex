from datetime import datetime

from pydantic import BaseModel


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


class AskRequest(BaseModel):
    question: str
    collection_id: int | None = None
