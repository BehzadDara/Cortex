import time
from collections.abc import Iterator
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langgraph.types import Command
from sqlalchemy.orm import Session

from app.api.common import (
    find_or_create_conversation,
    sse_event,
    start_title_generation,
    title_event,
)
from app.assistant_graph import (
    build_assistant_graph,
    extract_steps,
    final_answer,
    initial_state,
    state_question,
)
from app.checkpoints import get_checkpointer
from app.config import settings
from app.database import SessionLocal
from app.dependencies import (
    get_embedding_provider,
    get_fast_llm_provider,
    get_llm_provider,
    get_reranker,
    get_session,
    get_vector_store,
    get_web_search,
)
from app.models import Conversation, PromptLog
from app.rag.conversation import conversation_messages, save_exchange
from app.rag.embeddings import EmbeddingProvider
from app.rag.llm import LLMProvider
from app.rag.reranking import Reranker
from app.rag.vector_store import VectorStore
from app.rag.web_search import WebSearchProvider
from app.schemas import AskRequest, ResumeRequest
from app.tools import build_document_search, build_tools

router = APIRouter(tags=["assistant"])

TRANSCRIPT_MESSAGE_CHARS = 500


def build_graph(
    session: Session,
    embeddings: EmbeddingProvider,
    vector_store: VectorStore,
    reranker: Reranker,
    web_search: WebSearchProvider,
    llm: LLMProvider,
):
    tools = build_tools(web_search)
    search_documents = build_document_search(session, embeddings, vector_store, reranker)
    return build_assistant_graph(
        llm, tools, search_documents, checkpointer=get_checkpointer()
    )


def format_transcript(messages: list[dict]) -> str:
    lines = []
    for message in messages:
        line = f"{message.get('role')}: {(message.get('content') or '')[:TRANSCRIPT_MESSAGE_CHARS]}"
        tool_names = ", ".join(
            call["function"]["name"] for call in message.get("tool_calls") or []
        )
        if tool_names:
            line += f" [tools: {tool_names}]"
        lines.append(line)
    return "\n".join(lines)


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


def stream_events(
    graph,
    graph_input,
    thread_id: str,
    conversation_id: int,
    holder: dict | None,
    llm: LLMProvider,
) -> Iterator[str]:
    yield sse_event({"type": "conversation", "id": conversation_id})

    started = time.perf_counter()
    config = {"configurable": {"thread_id": thread_id}}
    final_state = None
    stream = graph.stream(
        graph_input, config, stream_mode=["custom", "updates", "values"]
    )
    for mode, chunk in stream:
        if mode == "custom":
            yield sse_event(chunk)
        elif mode == "updates" and "__interrupt__" in chunk:
            approval = chunk["__interrupt__"][0].value
            yield sse_event({"type": "approval", **approval, "thread": thread_id})
            return
        elif mode == "values":
            final_state = chunk
        event = title_event(conversation_id, holder)
        if event:
            yield event

    event = title_event(conversation_id, holder)
    if event:
        yield event
    yield sse_event({"type": "done"})

    if final_state is not None:
        question = state_question(final_state)
        answer = final_answer(final_state)
        save_prompt_log(
            question, format_transcript(final_state["messages"]), answer, started
        )
        save_exchange(
            conversation_id,
            question,
            answer,
            llm,
            steps=extract_steps(final_state["messages"]),
            sources=final_state.get("sources"),
        )


@router.post("/assistant")
def assistant(
    request: AskRequest,
    session: Session = Depends(get_session),
    embeddings: EmbeddingProvider = Depends(get_embedding_provider),
    vector_store: VectorStore = Depends(get_vector_store),
    llm: LLMProvider = Depends(get_llm_provider),
    fast_llm: LLMProvider = Depends(get_fast_llm_provider),
    reranker: Reranker = Depends(get_reranker),
    web_search: WebSearchProvider = Depends(get_web_search),
) -> StreamingResponse:
    conversation, is_new = find_or_create_conversation(
        session, request.conversation_id, request.question
    )
    title_holder: dict = {}
    if is_new:
        start_title_generation(fast_llm, conversation.id, request.question, title_holder)

    history = conversation_messages(conversation)
    graph = build_graph(session, embeddings, vector_store, reranker, web_search, llm)
    return StreamingResponse(
        stream_events(
            graph,
            initial_state(history, request.question),
            uuid4().hex,
            conversation.id,
            title_holder if is_new else None,
            llm,
        ),
        media_type="text/event-stream",
    )


@router.post("/assistant/resume")
def resume(
    request: ResumeRequest,
    session: Session = Depends(get_session),
    embeddings: EmbeddingProvider = Depends(get_embedding_provider),
    vector_store: VectorStore = Depends(get_vector_store),
    llm: LLMProvider = Depends(get_llm_provider),
    reranker: Reranker = Depends(get_reranker),
    web_search: WebSearchProvider = Depends(get_web_search),
) -> StreamingResponse:
    if session.get(Conversation, request.conversation_id) is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    graph = build_graph(session, embeddings, vector_store, reranker, web_search, llm)
    return StreamingResponse(
        stream_events(
            graph,
            Command(resume=request.approved),
            request.thread,
            request.conversation_id,
            None,
            llm,
        ),
        media_type="text/event-stream",
    )
