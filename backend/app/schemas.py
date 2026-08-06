from datetime import datetime

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: int
    filename: str
    chunk_count: int
    created_at: datetime


class AskRequest(BaseModel):
    question: str
