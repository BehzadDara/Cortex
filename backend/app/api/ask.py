import json
import time
from collections.abc import Iterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.common import find_or_create_conversation, start_title_generation
from app.config import settings
from app.database import SessionLocal
from app.dependencies import (
    get_embedding_provider,
    get_fast_llm_provider,
    get_llm_provider,
    get_reranker,
    get_session,
    get_vector_store,
)
from app.models import PromptLog
from app.rag.conversation import (
    format_history,
    recent_messages,
    rewrite_question,
    save_exchange,
)
from app.rag.embeddings import EmbeddingProvider
from app.rag.llm import LLMProvider
from app.rag.prompts import build_answer_prompt
from app.rag.reranking import Reranker
from app.rag.retrieval import retrieve_chunks
from app.rag.vector_store import VectorStore
from app.schemas import AskRequest

router = APIRouter(tags=["ask"])


def save_prompt_log(
    question: str, prompt: str, response: str, started: float, usage: dict
) -> None:
    latency_ms = int((time.perf_counter() - started) * 1000)
    with SessionLocal() as session:
        session.add(
            PromptLog(
                question=question,
                prompt=prompt,
                response=response,
                model=settings.llm_model,
                latency_ms=latency_ms,
                prompt_tokens=usage.get("prompt_tokens"),
                response_tokens=usage.get("response_tokens"),
            )
        )
        session.commit()


def sse_events(
    llm: LLMProvider, prompt: str, question: str, conversation_id: int
) -> Iterator[str]:
    yield f"data: {json.dumps({'type': 'conversation', 'id': conversation_id})}\n\n"

    started = time.perf_counter()
    usage: dict = {}
    tokens: list[str] = []
    for token in llm.stream(prompt, usage):
        tokens.append(token)
        yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
    yield f"data: {json.dumps({'type': 'done'})}\n\n"

    answer = "".join(tokens)
    save_prompt_log(question, prompt, answer, started, usage)
    save_exchange(conversation_id, question, answer, llm)


@router.post("/ask")
def ask(
    request: AskRequest,
    session: Session = Depends(get_session),
    embeddings: EmbeddingProvider = Depends(get_embedding_provider),
    vector_store: VectorStore = Depends(get_vector_store),
    llm: LLMProvider = Depends(get_llm_provider),
    fast_llm: LLMProvider = Depends(get_fast_llm_provider),
    reranker: Reranker = Depends(get_reranker),
) -> StreamingResponse:
    conversation, is_new = find_or_create_conversation(
        session, request.conversation_id
    )
    if is_new:
        start_title_generation(fast_llm, conversation.id, request.question)

    history = format_history(conversation, recent_messages(conversation))

    search_question = request.question
    if history:
        search_question = rewrite_question(llm, history, request.question)

    chunks = retrieve_chunks(
        session,
        search_question,
        settings.top_k,
        embeddings,
        vector_store,
        collection_id=request.collection_id,
        reranker=reranker,
    )
    prompt = build_answer_prompt(
        [chunk.content for chunk in chunks], request.question, history or None
    )
    return StreamingResponse(
        sse_events(llm, prompt, request.question, conversation.id),
        media_type="text/event-stream",
    )
