import json
import time
from pathlib import Path

from app.assistant_graph import decide_route
from app.dependencies import get_fast_llm_provider

GOLDEN_PATH = Path(__file__).parent / "routing.json"


def main() -> None:
    fast_llm = get_fast_llm_provider()
    items = json.loads(GOLDEN_PATH.read_text())

    correct = 0
    missed_documents = []
    needless_searches = []
    started = time.perf_counter()
    for item in items:
        decision = decide_route(fast_llm, item["question"], item.get("previous"))
        if decision == item["needs_documents"]:
            correct += 1
        elif item["needs_documents"]:
            missed_documents.append(item["question"])
        else:
            needless_searches.append(item["question"])

    total = len(items)
    average_ms = (time.perf_counter() - started) * 1000 / total
    print(f"accuracy: {correct}/{total} = {correct / total:.0%}")
    print(f"average routing latency: {average_ms:.0f} ms")
    for question in missed_documents:
        print(f"  MISSED DOCUMENTS (routed direct): {question}")
    for question in needless_searches:
        print(f"  needless search (routed to documents): {question}")


if __name__ == "__main__":
    main()
