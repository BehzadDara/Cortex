import operator
from dataclasses import dataclass
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from app.config import settings
from app.database import SessionLocal
from app.rag.embeddings import EmbeddingProvider
from app.rag.llm import LLMProvider
from app.rag.prompts import build_plan_prompt, build_synthesize_prompt
from app.rag.reranking import Reranker
from app.rag.retrieval import retrieve_chunks
from app.rag.vector_store import VectorStore
from app.rag.web_search import WebSearchProvider


@dataclass
class AgentStep:
    query: str
    findings: list[str]


@dataclass
class AgentResult:
    plan: list[str]
    steps: list[AgentStep]
    answer: str


class Finding(TypedDict):
    chunk_id: int | None
    text: str


class RetrievalStep(TypedDict):
    query: str
    findings: list[Finding]


class AgentState(TypedDict):
    question: str
    collection_id: int | None
    plan: list[str]
    steps: Annotated[list[RetrievalStep], operator.add]
    final_steps: list[AgentStep]
    answer: str


class QueryState(TypedDict):
    query: str
    collection_id: int | None


def clean_query(line: str) -> str:
    return line.strip().lstrip("-•*0123456789.) ").strip()


def parse_plan(raw: str, question: str) -> list[str]:
    queries = [clean_query(line) for line in raw.splitlines()]
    queries = [query for query in queries if query][: settings.agent_max_steps]
    return queries or [question]


def order_steps(
    plan: list[str], steps: list[RetrievalStep]
) -> list[RetrievalStep]:
    return sorted(steps, key=lambda step: plan.index(step["query"]))


def deduplicate(plan: list[str], steps: list[RetrievalStep]) -> list[AgentStep]:
    seen_chunk_ids: set[int] = set()
    deduped = []
    for step in order_steps(plan, steps):
        findings = []
        for finding in step["findings"]:
            chunk_id = finding["chunk_id"]
            if chunk_id is not None:
                if chunk_id in seen_chunk_ids:
                    continue
                seen_chunk_ids.add(chunk_id)
            findings.append(finding["text"])
        deduped.append(AgentStep(query=step["query"], findings=findings))
    return deduped


def format_evidence(steps: list[AgentStep]) -> str:
    sections = []
    for step in steps:
        findings = "\n".join(step.findings) or "Nothing found."
        sections.append(f"Search: {step.query}\n{findings}")
    return "\n\n---\n\n".join(sections)


def web_findings(web_search: WebSearchProvider, query: str) -> list[Finding]:
    try:
        results = web_search.search(query)
    except Exception:
        return []
    return [
        {"chunk_id": None, "text": f"[web: {result.url}]\n{result.title}\n{result.snippet}"}
        for result in results
    ]


def build_agent_graph(
    embeddings: EmbeddingProvider,
    vector_store: VectorStore,
    reranker: Reranker,
    llm: LLMProvider,
    web_search: WebSearchProvider,
):
    def plan(state: AgentState) -> dict:
        raw = llm.complete(
            build_plan_prompt(state["question"], settings.agent_max_steps)
        )
        return {"plan": parse_plan(raw, state["question"])}

    def fan_out(state: AgentState) -> list[Send]:
        return [
            Send("retrieve", {"query": query, "collection_id": state["collection_id"]})
            for query in state["plan"]
        ]

    def retrieve(state: QueryState) -> dict:
        with SessionLocal() as session:
            chunks = retrieve_chunks(
                session,
                state["query"],
                settings.agent_top_k,
                embeddings,
                vector_store,
                collection_id=state["collection_id"],
                reranker=reranker,
                min_score=settings.agent_min_relevance,
            )
            findings: list[Finding] = [
                {
                    "chunk_id": chunk.id,
                    "text": f"[{chunk.document.filename}]\n{chunk.content}",
                }
                for chunk in chunks
            ]
        if not findings:
            findings = web_findings(web_search, state["query"])
        return {"steps": [{"query": state["query"], "findings": findings}]}

    def reason(state: AgentState) -> dict:
        steps = deduplicate(state["plan"], state["steps"])
        answer = llm.complete(
            build_synthesize_prompt(state["question"], format_evidence(steps))
        )
        return {"final_steps": steps, "answer": answer}

    graph = StateGraph(AgentState)
    graph.add_node("plan", plan)
    graph.add_node("retrieve", retrieve)
    graph.add_node("reason", reason)
    graph.add_edge(START, "plan")
    graph.add_conditional_edges("plan", fan_out, ["retrieve"])
    graph.add_edge("retrieve", "reason")
    graph.add_edge("reason", END)
    return graph.compile()


def run_agent(
    question: str,
    embeddings: EmbeddingProvider,
    vector_store: VectorStore,
    reranker: Reranker,
    llm: LLMProvider,
    web_search: WebSearchProvider,
    collection_id: int | None = None,
) -> AgentResult:
    graph = build_agent_graph(embeddings, vector_store, reranker, llm, web_search)
    result = graph.invoke({"question": question, "collection_id": collection_id})
    return AgentResult(
        plan=result["plan"], steps=result["final_steps"], answer=result["answer"]
    )
