from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.assistant import build_graph, start_run, stream_events
from app.api.conversations import fallback_title, to_message_response, to_summary
from app.assistant_graph import initial_state
from app.dependencies import (
    get_embedding_provider,
    get_fast_llm_provider,
    get_image_generator,
    get_llm_provider,
    get_market_data_provider,
    get_reranker,
    get_session,
    get_vector_store,
    get_weather_provider,
    get_web_search,
)
from app.models import Conversation, Message
from app.rag.conversation import (
    conversation_messages,
    path_messages,
    path_to,
    select_message,
)
from app.rag.embeddings import EmbeddingProvider
from app.rag.image_generation import ImageGenerator
from app.rag.llm import LLMProvider
from app.rag.market_data import MarketDataProvider
from app.rag.reranking import Reranker
from app.rag.vector_store import VectorStore
from app.rag.weather import WeatherProvider
from app.rag.web_search import WebSearchProvider
from app.schemas import (
    ConversationSummary,
    EditRequest,
    FeedbackRequest,
    FeedbackResponse,
    PathResponse,
    RegenerateRequest,
)

router = APIRouter(prefix="/messages", tags=["messages"])


def branch_title(source: Conversation) -> str:
    return f"Branch of {source.title or fallback_title(source)}"[:80]


def copy_message(message: Message, conversation_id: int) -> Message:
    return Message(
        conversation_id=conversation_id,
        role=message.role,
        content=message.content,
        attachments=message.attachments,
        summary=message.summary,
        summarized_depth=message.summarized_depth,
        steps=message.steps,
        sources=message.sources,
        widgets=message.widgets,
        elapsed_ms=message.elapsed_ms,
        prompt_tokens=message.prompt_tokens,
        response_tokens=message.response_tokens,
    )


def require_message(session: Session, message_id: int, role: str) -> Message:
    message = session.get(Message, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found")
    if message.role != role:
        raise HTTPException(status_code=400, detail=f"Expected a {role} message")
    return message


def run_variant(
    session: Session,
    conversation: Conversation,
    parent_id: int | None,
    history: list[dict],
    question: str,
    timezone: str | None,
    providers: dict,
) -> StreamingResponse:
    graph = build_graph(session, **providers)
    thread_id = uuid4().hex
    start_run(session, conversation, thread_id, parent_id)
    return StreamingResponse(
        stream_events(
            graph,
            initial_state(history, question, timezone),
            thread_id,
            conversation.id,
            parent_id,
            None,
            providers["llm"],
        ),
        media_type="text/event-stream",
    )


def graph_providers(
    embeddings: EmbeddingProvider,
    vector_store: VectorStore,
    reranker: Reranker,
    web_search: WebSearchProvider,
    llm: LLMProvider,
    fast_llm: LLMProvider,
    weather: WeatherProvider,
    market_data: MarketDataProvider,
    image_generator: ImageGenerator,
) -> dict:
    return {
        "embeddings": embeddings,
        "vector_store": vector_store,
        "reranker": reranker,
        "web_search": web_search,
        "llm": llm,
        "fast_llm": fast_llm,
        "weather": weather,
        "market_data": market_data,
        "image_generator": image_generator,
    }


@router.put("/{message_id}/feedback", response_model=FeedbackResponse)
def set_feedback(
    message_id: int,
    request: FeedbackRequest,
    session: Session = Depends(get_session),
) -> FeedbackResponse:
    message = require_message(session, message_id, "assistant")
    message.feedback = request.value
    session.commit()
    return FeedbackResponse(id=message_id, feedback=message.feedback)


@router.put("/{message_id}/select", response_model=PathResponse)
def select_variant(
    message_id: int, session: Session = Depends(get_session)
) -> PathResponse:
    message = session.get(Message, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found")

    select_message(session, message)
    session.commit()
    return PathResponse(
        messages=[
            to_message_response(session, entry)
            for entry in path_messages(session, message.conversation)
        ]
    )


@router.post("/{message_id}/regenerate")
def regenerate(
    message_id: int,
    request: RegenerateRequest,
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
    message = require_message(session, message_id, "assistant")
    question_message = session.get(Message, message.parent_id)
    if question_message is None:
        raise HTTPException(status_code=400, detail="Nothing to regenerate from")

    history = conversation_messages(path_to(session, question_message)[:-1])
    return run_variant(
        session,
        message.conversation,
        question_message.id,
        history,
        question_message.content,
        request.timezone,
        graph_providers(
            embeddings, vector_store, reranker, web_search, llm, fast_llm,
            weather, market_data, image_generator,
        ),
    )


@router.post("/{message_id}/edit")
def edit_question(
    message_id: int,
    request: EditRequest,
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
    message = require_message(session, message_id, "user")
    history = conversation_messages(path_to(session, message)[:-1])
    return run_variant(
        session,
        message.conversation,
        message.parent_id,
        history,
        request.content.strip(),
        request.timezone,
        graph_providers(
            embeddings, vector_store, reranker, web_search, llm, fast_llm,
            weather, market_data, image_generator,
        ),
    )


@router.post("/{message_id}/branch", response_model=ConversationSummary)
def branch_conversation(
    message_id: int, session: Session = Depends(get_session)
) -> ConversationSummary:
    message = require_message(session, message_id, "assistant")
    source = message.conversation
    copied = path_to(session, message)

    branch = Conversation(
        title=branch_title(source),
        branched_from_id=source.id,
        branched_count=len(copied),
    )
    session.add(branch)
    session.flush()

    parent_id = None
    for entry in copied:
        copy = copy_message(entry, branch.id)
        copy.parent_id = parent_id
        session.add(copy)
        session.flush()
        if parent_id is None:
            branch.active_root_id = copy.id
        else:
            session.get(Message, parent_id).active_child_id = copy.id
        parent_id = copy.id

    session.commit()
    return to_summary(branch)
