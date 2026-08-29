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
    state_usage,
)
from app.checkpoints import get_checkpointer
from app.config import settings
from app.database import SessionLocal
from app.dependencies import (
    get_embedding_provider,
    get_fast_llm_provider,
    get_generated_image_store,
    get_image_generator,
    get_image_search,
    get_image_vector_store,
    get_knowledge_image_store,
    get_llm_provider,
    get_market_data_provider,
    get_reranker,
    get_session,
    get_vector_store,
    get_video_search,
    get_weather_provider,
    get_web_search,
)
from app.models import Conversation, PromptLog
from app.rag.conversation import (
    history_for,
    leaf_of,
    save_run,
    summarize_if_due,
)
from app.rag.embeddings import EmbeddingProvider
from app.rag.image_generation import ImageGenerator
from app.rag.llm import LLMProvider
from app.rag.market_data import MarketDataProvider
from app.rag.reranking import Reranker
from app.rag.vector_store import VectorStore
from app.rag.weather import WeatherProvider
from app.rag.web_search import WebSearchProvider
from app.schemas import AskRequest, ContinueRequest, ResumeRequest, StopRequest
from app.tools import (
    build_document_search,
    build_knowledge_image_search,
    build_tools,
    build_web_image_gallery,
    build_web_search,
)

router = APIRouter(tags=["assistant"])

TRANSCRIPT_MESSAGE_CHARS = 500


def build_graph(
    session: Session,
    embeddings: EmbeddingProvider,
    vector_store: VectorStore,
    reranker: Reranker,
    web_search: WebSearchProvider,
    llm: LLMProvider,
    fast_llm: LLMProvider,
    weather: WeatherProvider,
    market_data: MarketDataProvider,
    image_generator: ImageGenerator,
):
    tools = build_tools(
        session,
        weather,
        market_data,
        image_generator,
        get_image_search(),
        get_video_search(),
        get_generated_image_store(),
        get_knowledge_image_store(),
    )
    search_documents = build_document_search(session, embeddings, vector_store, reranker)
    search_images = build_knowledge_image_search(
        session, embeddings, get_image_vector_store(), reranker
    )
    search_web = build_web_search(web_search)
    search_web_images = build_web_image_gallery(
        get_image_search(), get_knowledge_image_store(), reranker
    )
    return build_assistant_graph(
        llm,
        fast_llm,
        tools,
        search_documents,
        search_web,
        search_images,
        search_web_images,
        checkpointer=get_checkpointer(),
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


def start_run(
    session: Session,
    conversation: Conversation,
    thread_id: str,
    parent_id: int | None,
) -> None:
    conversation.active_thread = thread_id
    conversation.active_parent_id = parent_id
    session.commit()


def clear_active_thread(conversation_id: int) -> None:
    with SessionLocal() as session:
        conversation = session.get(Conversation, conversation_id)
        if conversation is not None:
            conversation.active_thread = None
            conversation.active_parent_id = None
            session.commit()


def save_prompt_log(
    question: str,
    prompt: str,
    response: str,
    started: float,
    prompt_tokens: int,
    response_tokens: int,
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
                prompt_tokens=prompt_tokens,
                response_tokens=response_tokens,
            )
        )
        session.commit()


def stream_events(
    graph,
    graph_input,
    thread_id: str,
    conversation_id: int,
    parent_id: int | None,
    holder: dict | None,
    llm: LLMProvider,
    snapshot: dict | None = None,
) -> Iterator[str]:
    yield sse_event({"type": "conversation", "id": conversation_id})
    if snapshot is not None:
        yield sse_event({"type": "snapshot", **snapshot})

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
    if final_state is not None:
        usage = state_usage(final_state)
        yield sse_event(
            {
                "type": "usage",
                "elapsed_ms": usage.elapsed_ms,
                "prompt_tokens": usage.prompt_tokens,
                "response_tokens": usage.response_tokens,
            }
        )
        question = state_question(final_state)
        answer = final_answer(final_state)
        message_id = save_run(
            conversation_id,
            parent_id,
            question,
            answer,
            steps=extract_steps(final_state["messages"]),
            sources=final_state.get("sources"),
            widgets=final_state.get("widgets"),
            elapsed_ms=usage.elapsed_ms,
            prompt_tokens=usage.prompt_tokens,
            response_tokens=usage.response_tokens,
        )
        clear_active_thread(conversation_id)
        yield sse_event({"type": "saved", "message_id": message_id})
    yield sse_event({"type": "done"})

    if final_state is not None:
        save_prompt_log(
            question,
            format_transcript(final_state["messages"]),
            answer,
            started,
            usage.prompt_tokens,
            usage.response_tokens,
        )
        summarize_if_due(conversation_id, llm)


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
    weather: WeatherProvider = Depends(get_weather_provider),
    market_data: MarketDataProvider = Depends(get_market_data_provider),
    image_generator: ImageGenerator = Depends(get_image_generator),
) -> StreamingResponse:
    conversation, is_new = find_or_create_conversation(
        session, request.conversation_id, request.question
    )
    title_holder: dict = {}
    if is_new:
        start_title_generation(fast_llm, conversation.id, request.question, title_holder)

    leaf = leaf_of(session, conversation)
    parent_id = leaf.id if leaf else None
    history = history_for(session, conversation)
    graph = build_graph(
        session,
        embeddings,
        vector_store,
        reranker,
        web_search,
        llm,
        fast_llm,
        weather,
        market_data,
        image_generator,
    )
    thread_id = uuid4().hex
    start_run(session, conversation, thread_id, parent_id)
    return StreamingResponse(
        stream_events(
            graph,
            initial_state(history, request.question, request.timezone),
            thread_id,
            conversation.id,
            parent_id,
            title_holder if is_new else None,
            llm,
        ),
        media_type="text/event-stream",
    )


@router.post("/assistant/continue")
def continue_run(
    request: ContinueRequest,
    session: Session = Depends(get_session),
    embeddings: EmbeddingProvider = Depends(get_embedding_provider),
    vector_store: VectorStore = Depends(get_vector_store),
    llm: LLMProvider = Depends(get_llm_provider),
    fast_llm: LLMProvider = Depends(get_fast_llm_provider),
    reranker: Reranker = Depends(get_reranker),
    web_search: WebSearchProvider = Depends(get_web_search),
    weather: WeatherProvider = Depends(get_weather_provider),
    market_data: MarketDataProvider = Depends(get_market_data_provider),
    image_generator: ImageGenerator = Depends(get_image_generator),
) -> StreamingResponse:
    conversation = session.get(Conversation, request.conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conversation.active_thread is None:
        raise HTTPException(status_code=409, detail="No active run to continue")

    graph = build_graph(
        session,
        embeddings,
        vector_store,
        reranker,
        web_search,
        llm,
        fast_llm,
        weather,
        market_data,
        image_generator,
    )
    thread_id = conversation.active_thread
    state = graph.get_state({"configurable": {"thread_id": thread_id}})
    if not state.values:
        clear_active_thread(conversation.id)
        raise HTTPException(status_code=409, detail="No active run to continue")

    snapshot = {
        "question": state_question(state.values),
        "steps": extract_steps(state.values["messages"]),
        "sources": state.values.get("sources") or [],
        "widgets": state.values.get("widgets") or [],
    }
    return StreamingResponse(
        stream_events(
            graph,
            None,
            thread_id,
            conversation.id,
            conversation.active_parent_id,
            None,
            llm,
            snapshot=snapshot,
        ),
        media_type="text/event-stream",
    )


@router.post("/assistant/stop")
def stop_run(
    request: StopRequest, session: Session = Depends(get_session)
) -> dict:
    conversation = session.get(Conversation, request.conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conversation.active_thread = None
    conversation.active_parent_id = None
    session.commit()
    return {"stopped": True}


@router.post("/assistant/resume")
def resume(
    request: ResumeRequest,
    session: Session = Depends(get_session),
    embeddings: EmbeddingProvider = Depends(get_embedding_provider),
    vector_store: VectorStore = Depends(get_vector_store),
    llm: LLMProvider = Depends(get_llm_provider),
    fast_llm: LLMProvider = Depends(get_fast_llm_provider),
    reranker: Reranker = Depends(get_reranker),
    web_search: WebSearchProvider = Depends(get_web_search),
    weather: WeatherProvider = Depends(get_weather_provider),
    market_data: MarketDataProvider = Depends(get_market_data_provider),
    image_generator: ImageGenerator = Depends(get_image_generator),
) -> StreamingResponse:
    conversation = session.get(Conversation, request.conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    graph = build_graph(
        session,
        embeddings,
        vector_store,
        reranker,
        web_search,
        llm,
        fast_llm,
        weather,
        market_data,
        image_generator,
    )
    return StreamingResponse(
        stream_events(
            graph,
            Command(resume=request.approved),
            request.thread,
            request.conversation_id,
            conversation.active_parent_id,
            None,
            llm,
        ),
        media_type="text/event-stream",
    )
