import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import (
    get_embedding_provider,
    get_llm_provider,
    get_session,
    get_vector_store,
)
from app.rag.embeddings import EmbeddingProvider
from app.rag.llm import LLMProvider
from app.rag.prompts import build_answer_prompt
from app.rag.retrieval import retrieve_chunks
from app.rag.vector_store import VectorStore
from app.schemas import AskRequest

router = APIRouter(tags=["ask"])


def sse_events(llm: LLMProvider, prompt: str) -> Iterator[str]:
    for token in llm.stream(prompt):
        yield f"data: {json.dumps(token)}\n\n"
    yield "data: [DONE]\n\n"


@router.post("/ask")
def ask(
    request: AskRequest,
    session: Session = Depends(get_session),
    embeddings: EmbeddingProvider = Depends(get_embedding_provider),
    vector_store: VectorStore = Depends(get_vector_store),
    llm: LLMProvider = Depends(get_llm_provider),
) -> StreamingResponse:
    chunks = retrieve_chunks(
        session, request.question, settings.top_k, embeddings, vector_store
    )
    prompt = build_answer_prompt([chunk.content for chunk in chunks], request.question)
    return StreamingResponse(sse_events(llm, prompt), media_type="text/event-stream")
