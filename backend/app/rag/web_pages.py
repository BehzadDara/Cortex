import html as html_entities
import re

from sqlalchemy.orm import Session

from app.models import Message, WebPage
from app.rag.conversation import path_to
from app.rag.llm import LLMProvider
from app.rag.prompts import build_web_page_prompt

MAX_PAGE_CHARS = 200_000
MAX_TITLE_CHARS = 80
WEB_PAGE_WIDGET = "web_page"

DOCUMENT_START = re.compile(r"<!doctype html|<html", re.IGNORECASE)
DOCUMENT_END = re.compile(r"</html\s*>", re.IGNORECASE)
TITLE_ELEMENT = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
REMOTE_IMAGE = re.compile(r"""<img\b[^>]*\bsrc\s*=\s*["']?\s*(?:https?:)?//[^>]*>""", re.IGNORECASE)

PAGE_HEADERS = {
    "Content-Security-Policy": (
        "sandbox allow-scripts allow-forms allow-modals; default-src 'none'; "
        "style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:; "
        "form-action 'none'; frame-ancestors 'self'"
    ),
    "X-Content-Type-Options": "nosniff",
}


def extract_document(reply: str) -> str | None:
    start = DOCUMENT_START.search(reply)
    if start is None:
        return None
    ends = list(DOCUMENT_END.finditer(reply, start.start()))
    end = ends[-1].end() if ends else len(reply)
    document = REMOTE_IMAGE.sub("", reply[start.start() : end].strip())
    return document if len(document) <= MAX_PAGE_CHARS else None


def page_title(document: str, fallback: str) -> str:
    match = TITLE_ELEMENT.search(document)
    title = html_entities.unescape(match.group(1)).strip() if match else ""
    return " ".join((title or fallback).split())[:MAX_TITLE_CHARS]


def page_on_path(session: Session, parent_id: int | None) -> WebPage | None:
    if parent_id is None:
        return None
    parent = session.get(Message, parent_id)
    if parent is None:
        return None
    for message in reversed(path_to(session, parent)):
        for widget in reversed(message.widgets or []):
            if widget.get("kind") == WEB_PAGE_WIDGET:
                return session.get(WebPage, widget["data"]["page_id"])
    return None


def same_document(first: str, second: str) -> bool:
    return "".join(first.split()) == "".join(second.split())


def write_page(llm: LLMProvider, request: str, previous: WebPage | None) -> str | None:
    prompt = build_web_page_prompt(request, previous.html if previous else None)
    return extract_document(llm.complete(prompt))


def save_page(
    session: Session, request: str, document: str, previous: WebPage | None
) -> WebPage:
    page = WebPage(
        parent_id=previous.id if previous else None,
        version=previous.version + 1 if previous else 1,
        title=page_title(document, request),
        request=request,
        html=document,
    )
    session.add(page)
    session.commit()
    return page
