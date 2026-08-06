from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents import run_agent
from app.api.common import find_or_create_conversation, start_title_generation
from app.dependencies import (
    get_embedding_provider,
    get_fast_llm_provider,
    get_llm_provider,
    get_reranker,
    get_session,
    get_vector_store,
)
from app.rag.conversation import (
    format_history,
    recent_messages,
    rewrite_question,
    save_exchange,
)
from app.rag.embeddings import EmbeddingProvider
from app.rag.llm import LLMProvider
from app.rag.reranking import Reranker
from app.rag.vector_store import VectorStore
from app.schemas import AgentResponse, AgentStepResponse, AskRequest

router = APIRouter(tags=["agent"])


@router.post("/agent", response_model=AgentResponse)
def agent(
    request: AskRequest,
    session: Session = Depends(get_session),
    embeddings: EmbeddingProvider = Depends(get_embedding_provider),
    vector_store: VectorStore = Depends(get_vector_store),
    llm: LLMProvider = Depends(get_llm_provider),
    fast_llm: LLMProvider = Depends(get_fast_llm_provider),
    reranker: Reranker = Depends(get_reranker),
) -> AgentResponse:
    conversation, is_new = find_or_create_conversation(
        session, request.conversation_id
    )
    if is_new:
        start_title_generation(fast_llm, conversation.id, request.question)

    history = format_history(conversation, recent_messages(conversation))
    question = request.question
    if history:
        question = rewrite_question(llm, history, request.question)

    result = run_agent(
        session,
        question,
        embeddings,
        vector_store,
        reranker,
        llm,
        collection_id=request.collection_id,
    )
    save_exchange(conversation.id, request.question, result.answer, llm)
    return AgentResponse(
        conversation_id=conversation.id,
        plan=result.plan,
        steps=[
            AgentStepResponse(query=step.query, findings=step.findings)
            for step in result.steps
        ],
        answer=result.answer,
    )
