import json
import time
from pathlib import Path

from app.config import settings
from app.dependencies import get_fast_llm_provider
from app.rag.memory import extract_facts
from app.tracing import enable_tracing

GOLDEN_PATH = Path(__file__).parent / "memory.json"


def covers(facts: list[str], expected: list[str]) -> bool:
    blob = " ".join(facts).lower()
    return all(word in blob for word in expected)


def main() -> None:
    enable_tracing(settings.langsmith_eval_project)
    llm = get_fast_llm_provider()
    items = json.loads(GOLDEN_PATH.read_text())

    correct = 0
    missed = []
    invented = []
    started = time.perf_counter()
    for item in items:
        facts = extract_facts(llm, item["message"])
        expected = item["expected"]
        if covers(facts, expected) if expected else not facts:
            correct += 1
        elif expected:
            missed.append((item["message"], facts))
        else:
            invented.append((item["message"], facts))

    total = len(items)
    average_ms = (time.perf_counter() - started) * 1000 / total
    print(f"accuracy: {correct}/{total} = {correct / total:.0%}")
    print(f"average extraction latency: {average_ms:.0f} ms")
    for message, facts in missed:
        print(f"  MISSED a fact: {message} -> {facts}")
    for message, facts in invented:
        print(f"  invented a fact: {message} -> {facts}")


if __name__ == "__main__":
    main()
