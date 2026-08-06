from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config import settings
from app.rag.embeddings import EmbeddingProvider
from app.rag.llm import LLMProvider
from app.rag.prompts import build_plan_prompt, build_synthesize_prompt
from app.rag.reranking import Reranker
from app.rag.retrieval import retrieve_chunks
from app.rag.vector_store import VectorStore


@dataclass
class AgentStep:
    query: str
    findings: list[str]


@dataclass
class AgentResult:
    plan: list[str]
    steps: list[AgentStep]
    answer: str


def clean_query(line: str) -> str:
    return line.strip().lstrip("-•*0123456789.) ").strip()


def make_plan(llm: LLMProvider, question: str) -> list[str]:
    raw = llm.complete(build_plan_prompt(question, settings.agent_max_steps))
    queries = [clean_query(line) for line in raw.splitlines()]
    queries = [query for query in queries if query][: settings.agent_max_steps]
    return queries or [question]


def format_evidence(steps: list[AgentStep]) -> str:
    sections = []
    for step in steps:
        findings = "\n".join(step.findings) or "Nothing found."
        sections.append(f"Search: {step.query}\n{findings}")
    return "\n\n---\n\n".join(sections)


def run_agent(
    session: Session,
    question: str,
    embeddings: EmbeddingProvider,
    vector_store: VectorStore,
    reranker: Reranker,
    llm: LLMProvider,
    collection_id: int | None = None,
) -> AgentResult:
    plan = make_plan(llm, question)

    steps = []
    seen_chunk_ids: set[int] = set()
    for query in plan:
        chunks = retrieve_chunks(
            session,
            query,
            settings.agent_top_k,
            embeddings,
            vector_store,
            collection_id=collection_id,
            reranker=reranker,
        )
        fresh = [chunk for chunk in chunks if chunk.id not in seen_chunk_ids]
        seen_chunk_ids.update(chunk.id for chunk in fresh)
        findings = [
            f"[{chunk.document.filename}]\n{chunk.content}" for chunk in fresh
        ]
        steps.append(AgentStep(query=query, findings=findings))

    answer = llm.complete(
        build_synthesize_prompt(question, format_evidence(steps))
    )
    return AgentResult(plan=plan, steps=steps, answer=answer)
