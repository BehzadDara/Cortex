import re
from collections.abc import Callable
from dataclasses import dataclass

from app.config import settings
from app.rag.llm import LLMProvider
from app.rag.prompts import (
    build_overview_outline_prompt,
    build_overview_script_prompt,
    build_overview_summary_prompt,
)
from app.rag.speech import spoken_text


@dataclass
class EpisodeLength:
    segment_count: int
    minutes: int
    intro_lines: int
    body_lines: int
    outro_lines: int


EPISODE_LENGTHS = {
    "short": EpisodeLength(
        segment_count=4, minutes=5, intro_lines=8, body_lines=16, outro_lines=8
    ),
    "long": EpisodeLength(
        segment_count=6, minutes=10, intro_lines=8, body_lines=20, outro_lines=8
    ),
}


@dataclass
class SourceDocument:
    filename: str
    text: str


@dataclass
class Passage:
    chunk_id: int
    filename: str
    content: str


@dataclass
class Segment:
    title: str
    focus: str
    query: str


@dataclass
class Outline:
    title: str
    segments: list[Segment]


@dataclass
class ScriptLine:
    segment: int
    speaker: str
    text: str
    source: int | None


@dataclass
class Script:
    lines: list[ScriptLine]
    sources: list[Passage]


ProgressCallback = Callable[[float, str], None]
PassageSearch = Callable[[str], list[Passage]]

MAX_TITLE_CHARS = 80
PREVIOUS_LINES_SHOWN = 4
SCRIPT_ATTEMPTS = 2

STAGE_DIRECTION = re.compile(r"\([^)]*\)|\[[^\]]*\]|\*[^*]*\*")
SPEAKER_PREFIX = re.compile(r"^\s*[A-Za-z]+\s*:\s*")
WRAPPING_QUOTES = re.compile(r'^["“”]+|["“”]+$')

OUTLINE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "focus": {"type": "string"},
                    "query": {"type": "string"},
                },
                "required": ["title", "focus", "query"],
            },
        },
    },
    "required": ["title", "segments"],
}


def script_schema(hosts: tuple[str, str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "lines": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "speaker": {"type": "string", "enum": list(hosts)},
                        "text": {"type": "string"},
                        "source": {"type": "integer"},
                    },
                    "required": ["speaker", "text", "source"],
                },
            }
        },
        "required": ["lines"],
    }


def text_windows(text: str) -> list[str]:
    size = settings.overview_window_chars
    limit = settings.overview_windows_per_document
    return [text[start : start + size] for start in range(0, len(text), size)][:limit]


def summarize_documents(
    llm: LLMProvider, documents: list[SourceDocument], report: ProgressCallback
) -> str:
    work = [
        (document.filename, window)
        for document in documents
        for window in text_windows(document.text)
    ]
    sections: dict[str, list[str]] = {}
    for done, (filename, window) in enumerate(work):
        report(done / len(work), f"Reading {filename}")
        summary = llm.complete(build_overview_summary_prompt(filename, window))
        sections.setdefault(filename, []).append(summary)
    report(1.0, "Read every document")
    return "\n\n".join(
        f"Document: {filename}\n" + "\n".join(parts)
        for filename, parts in sections.items()
    )


def clean_phrase(text: str) -> str:
    return " ".join(str(text).split())


def plan_outline(
    llm: LLMProvider,
    summaries: str,
    hosts: tuple[str, str],
    length: EpisodeLength,
    focus: str | None,
) -> Outline:
    prompt = build_overview_outline_prompt(
        summaries, hosts, length.segment_count, length.minutes, focus
    )
    planned = llm.complete_json(prompt, OUTLINE_SCHEMA)
    segments = [
        Segment(
            title=clean_phrase(segment["title"]),
            focus=clean_phrase(segment["focus"]),
            query=clean_phrase(segment["query"]) or clean_phrase(segment["title"]),
        )
        for segment in planned.get("segments", [])
        if clean_phrase(segment.get("title", ""))
    ][: length.segment_count]
    if len(segments) < 2:
        raise ValueError("The model could not plan the episode. Try again.")
    title = clean_phrase(planned.get("title", "")) or segments[0].title
    return Outline(title=title[:MAX_TITLE_CHARS], segments=segments)


def segment_position(index: int, count: int) -> str:
    if index == 0:
        return "intro"
    if index == count - 1:
        return "outro"
    return "middle"


def segment_line_count(position: str, length: EpisodeLength) -> int:
    if position == "intro":
        return length.intro_lines
    if position == "outro":
        return length.outro_lines
    return length.body_lines


def outline_text(outline: Outline) -> str:
    return "\n".join(
        f"{number}. {segment.title}: {segment.focus}"
        for number, segment in enumerate(outline.segments, start=1)
    )


def passages_text(passages: list[Passage]) -> str:
    return "\n\n".join(
        f"[{number}] ({passage.filename})\n{passage.content}"
        for number, passage in enumerate(passages, start=1)
    )


def previous_lines_text(lines: list[ScriptLine]) -> str:
    return "\n".join(
        f"{line.speaker}: {line.text}" for line in lines[-PREVIOUS_LINES_SHOWN:]
    )


def spoken_line(text: str) -> str:
    text = STAGE_DIRECTION.sub(" ", str(text))
    text = SPEAKER_PREFIX.sub("", text)
    text = WRAPPING_QUOTES.sub("", text.strip())
    return clean_phrase(text)


def speaker_of(raw: str, hosts: tuple[str, str], previous: str | None) -> str:
    for host in hosts:
        if str(raw).strip().lower() == host.lower():
            return host
    return hosts[1] if previous == hosts[0] else hosts[0]


def register_sources(passages: list[Passage], sources: list[Passage]) -> list[int]:
    known = {source.chunk_id: index for index, source in enumerate(sources)}
    indices = []
    for passage in passages:
        if passage.chunk_id not in known:
            known[passage.chunk_id] = len(sources)
            sources.append(passage)
        indices.append(known[passage.chunk_id])
    return indices


def parsed_lines(
    reply: dict,
    segment: int,
    hosts: tuple[str, str],
    source_indices: list[int],
) -> list[ScriptLine]:
    lines: list[ScriptLine] = []
    for raw in reply.get("lines", []):
        text = spoken_line(raw.get("text", ""))
        if not spoken_text(text):
            continue
        previous = lines[-1].speaker if lines else None
        number = raw.get("source")
        source = (
            source_indices[number - 1]
            if isinstance(number, int) and 1 <= number <= len(source_indices)
            else None
        )
        lines.append(
            ScriptLine(
                segment=segment,
                speaker=speaker_of(raw.get("speaker", ""), hosts, previous),
                text=text,
                source=source,
            )
        )
    return lines


def write_segment(
    llm: LLMProvider,
    prompt: str,
    segment: int,
    hosts: tuple[str, str],
    source_indices: list[int],
) -> list[ScriptLine]:
    for _ in range(SCRIPT_ATTEMPTS):
        reply = llm.complete_json(prompt, script_schema(hosts))
        lines = parsed_lines(reply, segment, hosts, source_indices)
        if lines:
            return lines
    raise ValueError(f"The model wrote no lines for segment {segment + 1}. Try again.")


def write_script(
    llm: LLMProvider,
    outline: Outline,
    search: PassageSearch,
    hosts: tuple[str, str],
    length: EpisodeLength,
    report: ProgressCallback,
) -> Script:
    count = len(outline.segments)
    lines: list[ScriptLine] = []
    sources: list[Passage] = []
    for index, segment in enumerate(outline.segments):
        report(index / count, f"Writing segment {index + 1} of {count}: {segment.title}")
        passages = search(segment.query)
        source_indices = register_sources(passages, sources)
        position = segment_position(index, count)
        prompt = build_overview_script_prompt(
            hosts=hosts,
            episode_title=outline.title,
            outline=outline_text(outline),
            number=index + 1,
            segment_count=count,
            segment_title=segment.title,
            focus=segment.focus,
            position=position,
            passages=passages_text(passages),
            previous_lines=previous_lines_text(lines),
            line_count=segment_line_count(position, length),
        )
        lines.extend(write_segment(llm, prompt, index, hosts, source_indices))
    report(1.0, f"Wrote {len(lines)} lines")
    return Script(lines=lines, sources=sources)
