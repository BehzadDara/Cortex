from dataclasses import dataclass


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
