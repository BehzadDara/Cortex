from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.common import find_or_create_conversation, start_title_generation
from app.config import settings
from app.dependencies import (
    get_embedding_provider,
    get_fast_llm_provider,
    get_llm_provider,
    get_reranker,
    get_session,
    get_vector_store,
)
from app.rag.conversation import conversation_messages, save_exchange
from app.rag.embeddings import EmbeddingProvider
from app.rag.llm import LLMProvider, ToolCall
from app.rag.reranking import Reranker
from app.rag.vector_store import VectorStore
from app.schemas import ChatRequest, ChatResponse
from app.tools import Tool, build_tools, to_definition

router = APIRouter(tags=["chat"])

SYSTEM_PROMPT = (
    "You are Cortex, a helpful knowledge assistant. "
    "Use the available tools whenever they help you answer accurately. "
    "Use search_documents for questions about the user's documents. "
    "Answer concisely once you have what you need."
)


def execute_tool(tool_map: dict[str, Tool], call: ToolCall) -> str:
    tool = tool_map.get(call.name)
    if tool is None:
        return f"Unknown tool: {call.name}"
    try:
        return tool.run(**call.arguments)
    except Exception as error:
        return f"Tool error: {error}"


def run_tool_loop(
    llm: LLMProvider, tools: list[Tool], question: str, history: list[dict]
) -> tuple[str, list[str]]:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history,
        {"role": "user", "content": question},
    ]
    definitions = [to_definition(tool) for tool in tools]
    tool_map = {tool.name: tool for tool in tools}
    used: list[str] = []

    for _ in range(settings.chat_max_rounds):
        reply = llm.chat(messages, definitions)
        if not reply.tool_calls:
            return reply.content, used

        messages.append(reply.raw_message)
        for call in reply.tool_calls:
            used.append(call.name)
            messages.append(
                {
                    "role": "tool",
                    "tool_name": call.name,
                    "content": execute_tool(tool_map, call),
                }
            )

    return "I could not finish answering within the tool call limit.", used


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    session: Session = Depends(get_session),
    embeddings: EmbeddingProvider = Depends(get_embedding_provider),
    vector_store: VectorStore = Depends(get_vector_store),
    llm: LLMProvider = Depends(get_llm_provider),
    fast_llm: LLMProvider = Depends(get_fast_llm_provider),
    reranker: Reranker = Depends(get_reranker),
) -> ChatResponse:
    conversation, is_new = find_or_create_conversation(
        session, request.conversation_id, request.question
    )
    if is_new:
        start_title_generation(fast_llm, conversation.id, request.question, {})

    history = conversation_messages(conversation)
    tools = build_tools(session, embeddings, vector_store, reranker)
    answer, used = run_tool_loop(llm, tools, request.question, history)
    save_exchange(conversation.id, request.question, answer, llm)
    return ChatResponse(
        conversation_id=conversation.id, answer=answer, tools_used=used
    )
