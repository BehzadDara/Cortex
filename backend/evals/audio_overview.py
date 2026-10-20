import sys
import time
from collections import Counter

from sqlalchemy import select

from app.database import SessionLocal
from app.dependencies import get_fast_llm_provider
from app.models import AudioOverview
from app.rag.llm import LLMProvider

JUDGE_PROMPT = """You check a podcast script for invented facts.

Reference text:
{passage}

A host said this line:
{line}

First classify the line:
- "question": it asks something, even if the question hints at an answer.
- "reaction": a short reaction, agreement, or opinion ("Wow.", "Exactly.", "That's clever.").
- "greeting": a welcome, thanks, or goodbye.
- "statement": it states a fact about the subject.

Then, for a statement only, set "supported" to true when every fact, number, and name in it is stated in the reference text or directly follows from it. Rewording, simplifying, and analogies are fine. Set it to false when the line adds a fact the reference text doesn't contain or contradicts it. For any other kind, set "supported" to true.

Answer in JSON."""

NO_PASSAGE = "(none)"

VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {
            "type": "string",
            "enum": ["question", "reaction", "greeting", "statement"],
        },
        "supported": {"type": "boolean"},
    },
    "required": ["kind", "supported"],
}


def latest_finished(session) -> AudioOverview | None:
    query = (
        select(AudioOverview)
        .where(AudioOverview.status == "done")
        .order_by(AudioOverview.created_at.desc())
        .limit(1)
    )
    return session.scalars(query).first()


def chosen_overview(session) -> AudioOverview | None:
    if len(sys.argv) > 1:
        return session.get(AudioOverview, int(sys.argv[1]))
    return latest_finished(session)


def ask_judge(judge_llm: LLMProvider, line: str, passage: str) -> dict:
    prompt = JUDGE_PROMPT.format(passage=passage, line=line)
    return judge_llm.complete_json(prompt, VERDICT_SCHEMA)


def judge(judge_llm: LLMProvider, line: dict, sources: list[dict]) -> str:
    cited = sources[line["source"]]["content"] if line["source"] is not None else NO_PASSAGE
    first = ask_judge(judge_llm, line["text"], cited)
    if first["kind"] != "statement":
        return "no_claim"
    if first["supported"]:
        return "cited"
    everything = "\n\n".join(source["content"] for source in sources)
    if ask_judge(judge_llm, line["text"], everything)["supported"]:
        return "elsewhere"
    return "unsupported"


def percent(part: int, whole: int) -> str:
    return f"{part}/{whole} = {part / whole:.0%}" if whole else "n/a"


def main() -> None:
    with SessionLocal() as session:
        overview = chosen_overview(session)
        if overview is None:
            print("No finished audio overview to judge.")
            return
        lines, sources = overview.lines or [], overview.sources or []
        print(f"Judging overview {overview.id}: {overview.title} ({len(lines)} lines)")

    judge_llm = get_fast_llm_provider()
    started = time.perf_counter()
    verdicts: Counter[str] = Counter()
    for line in lines:
        verdict = judge(judge_llm, line, sources)
        verdicts[verdict] += 1
        if verdict == "unsupported":
            print(f"  UNSUPPORTED  {line['speaker']}: {line['text']}")

    claims = verdicts["cited"] + verdicts["elsewhere"] + verdicts["unsupported"]
    print(f"fact-stating lines: {claims} of {len(lines)}")
    print(f"faithfulness: {percent(verdicts['cited'] + verdicts['elsewhere'], claims)}")
    print(f"cited passage supports the line: {percent(verdicts['cited'], claims)}")
    print(f"judged in {time.perf_counter() - started:.1f}s")


if __name__ == "__main__":
    main()
