from io import BytesIO
from pathlib import Path
from typing import Protocol

from docx import Document as DocxDocument
from pypdf import PdfReader


class DocumentParser(Protocol):
    def parse(self, data: bytes) -> str: ...


class TextParser:
    def parse(self, data: bytes) -> str:
        return data.decode("utf-8")


class PdfParser:
    def parse(self, data: bytes) -> str:
        reader = PdfReader(BytesIO(data))
        return "\n\n".join(page.extract_text() for page in reader.pages)


class DocxParser:
    def parse(self, data: bytes) -> str:
        document = DocxDocument(BytesIO(data))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)


PARSERS: dict[str, DocumentParser] = {
    ".txt": TextParser(),
    ".md": TextParser(),
    ".pdf": PdfParser(),
    ".docx": DocxParser(),
}


def parser_for(filename: str) -> DocumentParser | None:
    return PARSERS.get(Path(filename).suffix.lower())


def supported_suffixes() -> str:
    return ", ".join(sorted(PARSERS))
