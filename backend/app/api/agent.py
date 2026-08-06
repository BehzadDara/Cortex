from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.agents import run_agent
from app.dependencies import (
    get_embedding_provider,
    get_llm_provider,
    get_reranker,
    get_session,
    get_vector_store,
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
    reranker: Reranker = Depends(get_reranker),
) -> AgentResponse:
    result = run_agent(
        session,
        request.question,
        embeddings,
        vector_store,
        reranker,
        llm,
        collection_id=request.collection_id,
    )
    return AgentResponse(
        plan=result.plan,
        steps=[
            AgentStepResponse(query=step.query, findings=step.findings)
            for step in result.steps
        ],
        answer=result.answer,
    )
