import json
import threading
import time
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

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
from app.models import Conversation, Message, PromptLog
from app.rag.conversation import (
    format_history,
    maybe_summarize,
    recent_messages,
    rewrite_question,
    save_title,
)
from app.rag.embeddings import EmbeddingProvider
from app.rag.llm import LLMProvider
from app.rag.prompts import build_answer_prompt
from app.rag.reranking import Reranker
from app.rag.retrieval import retrieve_chunks
from app.rag.vector_store import VectorStore
from app.schemas import AskRequest

router = APIRouter(tags=["ask"])


def find_or_create_conversation(
    session: Session, conversation_id: int | None
) -> Conversation:
    if conversation_id is not None:
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conversation

    conversation = Conversation()
    session.add(conversation)
    session.commit()
    return conversation


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


def save_exchange(
    conversation_id: int, question: str, answer: str, llm: LLMProvider
) -> None:
    with SessionLocal() as session:
        conversation = session.get(Conversation, conversation_id)
        session.add_all(
            [
                Message(
                    conversation_id=conversation_id, role="user", content=question
                ),
                Message(
                    conversation_id=conversation_id, role="assistant", content=answer
                ),
            ]
        )
        session.commit()
        maybe_summarize(session, llm, conversation)


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
    is_new = request.conversation_id is None
    conversation = find_or_create_conversation(session, request.conversation_id)
    if is_new:
        threading.Thread(
            target=save_title,
            args=(fast_llm, conversation.id, request.question),
            daemon=True,
        ).start()

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
