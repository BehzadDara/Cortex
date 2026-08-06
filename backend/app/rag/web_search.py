from dataclasses import dataclass
from typing import Protocol

from app.config import settings


@dataclass
class WebResult:
    title: str
    url: str
    snippet: str


class WebSearchProvider(Protocol):
    def search(self, query: str) -> list[WebResult]: ...


class DdgsWebSearch:
    def search(self, query: str) -> list[WebResult]:
        from ddgs import DDGS

        with DDGS() as client:
            hits = client.text(query, max_results=settings.web_search_results)
        return [
            WebResult(title=hit["title"], url=hit["href"], snippet=hit["body"])
            for hit in hits
        ]
