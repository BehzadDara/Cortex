import argparse
import json
import re
import statistics
import time
from pathlib import Path
from uuid import uuid4

from langgraph.types import Command
from sqlalchemy.orm import Session

from app.api.assistant import build_graph
from app.assistant_graph import final_answer, initial_state
from app.config import settings
from app.database import SessionLocal
from app.dependencies import (
    get_embedding_provider,
    get_fast_llm_provider,
    get_image_generator,
    get_llm_provider,
    get_market_data_provider,
    get_reranker,
    get_vector_store,
    get_weather_provider,
    get_web_search,
)
from app.models import Chunk
from app.rag.prompts import build_answer_prompt
from app.rag.retrieval import retrieve_chunks

GOLDEN_PATH = Path(__file__).parent / "golden.json"

CITATION_NUMBER = re.compile(r"\[(\d+)\]")


def normalize(text: str) -> str:
    return " ".join(text.split()).lower()


def retrieval_rank(chunks: list[Chunk], item: dict) -> int | None:
    for rank, chunk in enumerate(chunks, start=1):
        same_source = chunk.document.filename == item["source_document"]
        if same_source and normalize(item["source_phrase"]) in normalize(chunk.content):
            return rank
    return None


def answer_is_correct(answer: str, item: dict) -> bool:
    return all(
        normalize(phrase) in normalize(answer) for phrase in item["expected_phrases"]
    )


def cited_numbers(answer: str) -> set[int]:
    return {int(match) for match in CITATION_NUMBER.findall(answer)}


def correct_source_id(sources: list[dict], item: dict) -> int | None:
    return next(
        (
            source["id"]
            for source in sources
            if source["filename"] == item["source_document"]
            and normalize(item["source_phrase"]) in normalize(source["content"])
        ),
        None,
    )


def build_eval_graph(session: Session):
    return build_graph(
        session,
        get_embedding_provider(),
        get_vector_store(),
        get_reranker() if settings.rerank else None,
        get_web_search(),
        get_llm_provider(),
        get_fast_llm_provider(),
        get_weather_provider(),
        get_market_data_provider(),
        get_image_generator(),
    )


def run_assistant(graph, question: str) -> dict:
    thread_id = uuid4().hex
    config = {"configurable": {"thread_id": thread_id}}
    graph_input = initial_state([], question)
    final_state = None
    while True:
        interrupted = False
        for mode, chunk in graph.stream(
            graph_input, config, stream_mode=["updates", "values"]
        ):
            if mode == "updates" and "__interrupt__" in chunk:
                interrupted = True
                break
            if mode == "values":
                final_state = chunk
        if not interrupted:
            return final_state
        graph_input = Command(resume=False)


def evaluate(session: Session, items: list[dict], with_generation: bool) -> None:
    embeddings = get_embedding_provider()
    vector_store = get_vector_store()
    llm = get_llm_provider()
    reranker = get_reranker() if settings.rerank else None
    if reranker:
        reranker.rerank("warm up", ["warm up"])

    hits = 0
    first_hits = 0
    reciprocal_sum = 0.0
    correct = 0
    retrieval_seconds: list[float] = []
    generation_seconds: list[float] = []

    for item in items:
        started = time.perf_counter()
        chunks = retrieve_chunks(
            session,
            item["question"],
            settings.top_k,
            embeddings,
            vector_store,
            reranker=reranker,
        )
        retrieval_seconds.append(time.perf_counter() - started)

        rank = retrieval_rank(chunks, item)
        if rank:
            hits += 1
            first_hits += rank == 1
            reciprocal_sum += 1 / rank
        status = f"hit@{rank}" if rank else "MISS"

        if with_generation:
            prompt = build_answer_prompt(
                [chunk.content for chunk in chunks], item["question"]
            )
            started = time.perf_counter()
            answer = "".join(llm.stream(prompt))
            generation_seconds.append(time.perf_counter() - started)
            if answer_is_correct(answer, item):
                correct += 1
                status += " correct"
            else:
                status += f" WRONG: {answer[:80]!r}"

        print(f"[{status}] {item['question']}")

    total = len(items)
    print()
    print(f"hit rate@{settings.top_k}: {hits}/{total} = {hits / total:.0%}")
    print(f"hit@1: {first_hits}/{total} = {first_hits / total:.0%}")
    print(f"MRR: {reciprocal_sum / total:.3f}")
    print(f"avg retrieval: {statistics.mean(retrieval_seconds) * 1000:.0f} ms")
    if with_generation:
        print(f"answer accuracy: {correct}/{total} = {correct / total:.0%}")
        print(f"avg generation: {statistics.mean(generation_seconds):.1f} s")


def evaluate_assistant(session: Session, items: list[dict]) -> None:
    graph = build_eval_graph(session)

    correct = 0
    grounded = 0
    hallucinated = 0
    run_seconds: list[float] = []

    for item in items:
        started = time.perf_counter()
        final_state = run_assistant(graph, item["question"])
        run_seconds.append(time.perf_counter() - started)

        answer = final_answer(final_state)
        sources = final_state.get("sources") or []
        cited = cited_numbers(answer)
        target_id = correct_source_id(sources, item)
        is_correct = answer_is_correct(answer, item)
        is_grounded = target_id is not None and target_id in cited
        has_hallucination = bool(cited - {source["id"] for source in sources})

        correct += is_correct
        grounded += is_grounded
        hallucinated += has_hallucination

        status = "correct" if is_correct else f"WRONG: {answer[:80]!r}"
        if not is_grounded:
            status += " [not grounded]"
        if has_hallucination:
            status += " [hallucinated citation]"
        print(f"[{status}] {item['question']}")

    total = len(items)
    print()
    print(f"answer accuracy: {correct}/{total} = {correct / total:.0%}")
    print(f"correctly grounded: {grounded}/{total} = {grounded / total:.0%}")
    print(f"hallucinated citations: {hallucinated}/{total}")
    print(f"avg run: {statistics.mean(run_seconds):.1f} s")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--retrieval-only", action="store_true")
    parser.add_argument(
        "--assistant",
        action="store_true",
        help=(
            "Run the golden set through the live /assistant graph "
            "(route, retrieve, tool loop, citations) instead of the "
            "standalone answer prompt."
        ),
    )
    arguments = parser.parse_args()

    items = json.loads(GOLDEN_PATH.read_text())
    with SessionLocal() as session:
        if arguments.assistant:
            evaluate_assistant(session, items)
        else:
            evaluate(session, items, with_generation=not arguments.retrieval_only)


if __name__ == "__main__":
    main()
