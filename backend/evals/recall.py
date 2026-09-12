import json
import statistics
import uuid
from pathlib import Path

import httpx

from app.config import settings
from app.dependencies import get_fast_llm_provider

GOLDEN_PATH = Path(__file__).parent / "recall.json"


def isolated_collection() -> str:
    settings.qdrant_memory_collection = f"recall_eval_{uuid.uuid4().hex[:8]}"
    settings.user_memory_history_path = str(
        Path(settings.user_memory_history_path).with_name("recall_eval.db")
    )
    return settings.qdrant_memory_collection


def drop_collection(name: str) -> None:
    httpx.delete(f"{settings.qdrant_url}/collections/{name}", timeout=30)


def store_facts(store, facts: list[str]) -> None:
    for fact in facts:
        store.memory.add(
            [{"role": "user", "content": fact}], user_id=store.user_id, infer=False
        )


def main() -> None:
    golden = json.loads(GOLDEN_PATH.read_text())
    collection = isolated_collection()
    from app.rag.memory import Mem0MemoryStore

    store = Mem0MemoryStore(get_fast_llm_provider())
    try:
        store_facts(store, golden["facts"])

        kept = 0
        recalled_counts = []
        for probe in golden["relevant"]:
            facts = [memory.text.lower() for memory in store.recall(probe["question"])]
            recalled_counts.append(len(facts))
            found = any(probe["expected"] in fact for fact in facts)
            kept += found
            if not found:
                print(f"  LOST the fact for: {probe['question']} -> {facts}")

        empty = 0
        for question in golden["irrelevant"]:
            facts = store.recall(question)
            empty += not facts
            if facts:
                print(f"  recalled anyway: {question} -> {[m.text for m in facts]}")

        relevant_total = len(golden["relevant"])
        irrelevant_total = len(golden["irrelevant"])
        print()
        print(f"threshold: {settings.user_memory_min_relevance}")
        print(f"relevant facts kept: {kept}/{relevant_total} = {kept / relevant_total:.0%}")
        print(
            f"irrelevant questions recalling nothing: {empty}/{irrelevant_total} = "
            f"{empty / irrelevant_total:.0%}"
        )
        print(f"facts per relevant question: {statistics.mean(recalled_counts):.1f}")
    finally:
        drop_collection(collection)


if __name__ == "__main__":
    main()
