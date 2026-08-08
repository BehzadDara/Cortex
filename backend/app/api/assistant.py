from collections.abc import Iterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.common import (
    find_or_create_conversation,
    sse_event,
    start_title_generation,
    title_event,
)
from app.assistant_graph import (
    build_assistant_graph,
    final_answer,
    initial_state,
)
from app.dependencies import (
    get_embedding_provider,
    get_fast_llm_provider,
    get_llm_provider,
    get_reranker,
    get_session,
    get_vector_store,
    get_web_search,
)
from app.rag.conversation import conversation_messages, save_exchange
from app.rag.embeddings import EmbeddingProvider
from app.rag.llm import LLMProvider
from app.rag.reranking import Reranker
from app.rag.vector_store import VectorStore
from app.rag.web_search import WebSearchProvider
from app.schemas import AskRequest
from app.tools import build_tools

router = APIRouter(tags=["assistant"])


def record_step(steps: list[dict], event: dict) -> None:
    if event["type"] == "tool_call":
        steps.append(
            {"name": event["name"], "arguments": event["arguments"], "result": None}
        )
    elif event["type"] == "tool_result":
        for step in reversed(steps):
            if step["name"] == event["name"] and step["result"] is None:
                step["result"] = event["content"]
                break


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
    tools = build_tools(
        session,
        embeddings,
        vector_store,
        reranker,
        web_search,
        collection_id=request.collection_id,
    )
    graph = build_assistant_graph(llm, tools)
    holder = title_holder if is_new else None

    def events() -> Iterator[str]:
        yield sse_event({"type": "conversation", "id": conversation.id})

        steps: list[dict] = []
        final_state = None
        stream = graph.stream(
            initial_state(history, request.question),
            stream_mode=["custom", "values"],
        )
        for mode, chunk in stream:
            if mode == "custom":
                record_step(steps, chunk)
                yield sse_event(chunk)
            else:
                final_state = chunk
            event = title_event(conversation.id, holder)
            if event:
                yield event

        event = title_event(conversation.id, holder)
        if event:
            yield event
        yield sse_event({"type": "done"})

        if final_state is not None:
            answer = final_answer(final_state)
            save_exchange(
                conversation.id, request.question, answer, llm, steps=steps
            )

    return StreamingResponse(events(), media_type="text/event-stream")
