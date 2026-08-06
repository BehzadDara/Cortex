import argparse
import json
import statistics
import time
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.dependencies import (
    get_embedding_provider,
    get_llm_provider,
    get_reranker,
    get_vector_store,
)
from app.models import Chunk
from app.rag.prompts import build_answer_prompt
from app.rag.retrieval import retrieve_chunks

GOLDEN_PATH = Path(__file__).parent / "golden.json"


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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--retrieval-only", action="store_true")
    arguments = parser.parse_args()

    items = json.loads(GOLDEN_PATH.read_text())
    with SessionLocal() as session:
        evaluate(session, items, with_generation=not arguments.retrieval_only)


if __name__ == "__main__":
    main()
