from dataclasses import dataclass
from pathlib import Path

from app.config import settings

CODE_SUFFIXES = {".py", ".js", ".ts", ".tsx", ".java", ".go", ".rs"}


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
