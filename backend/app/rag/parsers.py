from io import BytesIO
from pathlib import Path
from typing import Protocol

from docx import Document as DocxDocument
from pypdf import PdfReader

from app.config import settings
from app.rag.prompts import TRANSCRIBE_PROMPT
from app.rag.vision import VisionProvider


class DocumentParser(Protocol):
    def parse(self, data: bytes) -> str: ...


class TextParser:
    def parse(self, data: bytes) -> str:
        return data.decode("utf-8")


class DocxParser:
    def parse(self, data: bytes) -> str:
        document = DocxDocument(BytesIO(data))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)


class ImageParser:
    def __init__(self, vision: VisionProvider) -> None:
        self.vision = vision

    def parse(self, data: bytes) -> str:
        return self.vision.describe(data, TRANSCRIBE_PROMPT)


class PdfParser:
    def __init__(self, vision: VisionProvider) -> None:
        self.vision = vision

    def parse(self, data: bytes) -> str:
        reader = PdfReader(BytesIO(data))
        text = "\n\n".join(page.extract_text() for page in reader.pages)
        if text.strip():
            return text
        return self.ocr(data)

    def ocr(self, data: bytes) -> str:
        import pypdfium2 as pdfium

        document = pdfium.PdfDocument(data)
        pages = []
        for index in range(min(len(document), settings.ocr_max_pages)):
            bitmap = document[index].render(scale=2)
            buffer = BytesIO()
            bitmap.to_pil().save(buffer, "PNG")
            pages.append(self.vision.describe(buffer.getvalue(), TRANSCRIBE_PROMPT))
        return "\n\n".join(pages)


def build_parsers(vision: VisionProvider) -> dict[str, DocumentParser]:
    text_parser = TextParser()
    image_parser = ImageParser(vision)
    return {
        ".txt": text_parser,
        ".md": text_parser,
        ".pdf": PdfParser(vision),
        ".docx": DocxParser(),
        ".png": image_parser,
        ".jpg": image_parser,
        ".jpeg": image_parser,
    }


def parser_for(
    filename: str, parsers: dict[str, DocumentParser]
) -> DocumentParser | None:
    return parsers.get(Path(filename).suffix.lower())


def supported_suffixes(parsers: dict[str, DocumentParser]) -> str:
    return ", ".join(sorted(parsers))
