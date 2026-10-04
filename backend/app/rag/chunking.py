from dataclasses import dataclass
from pathlib import Path

from app.config import settings

CODE_SUFFIXES = {".py", ".js", ".ts", ".tsx", ".java", ".go", ".rs"}

MIN_STITCH_OVERLAP = 20


@dataclass
class TextChunk:
    content: str
    position: int


def split_text(text: str, chunk_size: int, overlap: int) -> list[TextChunk]:
    step = chunk_size - overlap
    chunks = []
    for position, start in enumerate(range(0, len(text), step)):
        content = text[start : start + chunk_size].strip()
        if content:
            chunks.append(TextChunk(content=content, position=position))
    return chunks


def split_lines(text: str, chunk_lines: int, overlap: int) -> list[TextChunk]:
    lines = text.splitlines()
    step = chunk_lines - overlap
    chunks = []
    for position, start in enumerate(range(0, len(lines), step)):
        content = "\n".join(lines[start : start + chunk_lines]).strip()
        if content:
            chunks.append(TextChunk(content=content, position=position))
    return chunks


def split_for(filename: str, text: str) -> list[TextChunk]:
    if Path(filename).suffix.lower() in CODE_SUFFIXES:
        return split_lines(
            text, settings.code_chunk_lines, settings.code_chunk_overlap_lines
        )
    return split_text(text, settings.chunk_size, settings.chunk_overlap)


def overlap_length(previous: str, following: str) -> int:
    tail = previous[-len(following) :]
    start = tail.find(following[0])
    while start != -1 and len(tail) - start >= MIN_STITCH_OVERLAP:
        if following.startswith(tail[start:]):
            return len(tail) - start
        start = tail.find(following[0], start + 1)
    return 0


def stitch_chunks(contents: list[str]) -> tuple[str, list[int]]:
    text = ""
    starts: list[int] = []
    for content in contents:
        overlap = overlap_length(text, content) if text else 0
        if text and not overlap:
            text += "\n"
        starts.append(len(text) - overlap)
        text += content[overlap:]
    return text, starts
