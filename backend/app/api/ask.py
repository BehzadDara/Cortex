import json
import time
from collections.abc import Iterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.dependencies import (
    get_embedding_provider,
    get_llm_provider,
    get_reranker,
    get_session,
    get_vector_store,
)
from app.models import PromptLog
from app.rag.embeddings import EmbeddingProvider
from app.rag.llm import LLMProvider
from app.rag.prompts import build_answer_prompt
from app.rag.reranking import Reranker
from app.rag.retrieval import retrieve_chunks
from app.rag.vector_store import VectorStore
from app.schemas import AskRequest

router = APIRouter(tags=["ask"])


def save_prompt_log(question: str, prompt: str, response: str, started: float) -> None:
    latency_ms = int((time.perf_counter() - started) * 1000)
    with SessionLocal() as session:
        session.add(
            PromptLog(
                question=question,
                prompt=prompt,
                response=response,
                model=settings.llm_model,
                latency_ms=latency_ms,
            )
        )
        session.commit()


def sse_events(llm: LLMProvider, prompt: str, question: str) -> Iterator[str]:
    started = time.perf_counter()
    tokens: list[str] = []
    for token in llm.stream(prompt):
        tokens.append(token)
        yield f"data: {json.dumps(token)}\n\n"
    yield "data: [DONE]\n\n"
    save_prompt_log(question, prompt, "".join(tokens), started)


@router.post("/ask")
def ask(
    request: AskRequest,
    session: Session = Depends(get_session),
    embeddings: EmbeddingProvider = Depends(get_embedding_provider),
    vector_store: VectorStore = Depends(get_vector_store),
    llm: LLMProvider = Depends(get_llm_provider),
    reranker: Reranker = Depends(get_reranker),
) -> StreamingResponse:
    chunks = retrieve_chunks(
        session,
        request.question,
        settings.top_k,
        embeddings,
        vector_store,
        collection_id=request.collection_id,
        reranker=reranker,
    )
    prompt = build_answer_prompt([chunk.content for chunk in chunks], request.question)
    return StreamingResponse(
        sse_events(llm, prompt, request.question), media_type="text/event-stream"
    )
