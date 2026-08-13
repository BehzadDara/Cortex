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


@dataclass
class WebImage:
    title: str
    image_url: str
    thumbnail_url: str | None
    page_url: str


class ImageSearchProvider(Protocol):
    def search(self, query: str) -> list[WebImage]: ...


class DdgsImageSearch:
    def search(self, query: str) -> list[WebImage]:
        from ddgs import DDGS

        with DDGS() as client:
            hits = client.images(query, max_results=settings.web_image_results)
        return [
            WebImage(
                title=hit.get("title") or query,
                image_url=hit["image"],
                thumbnail_url=hit.get("thumbnail"),
                page_url=hit.get("url") or hit["image"],
            )
            for hit in hits
            if hit.get("image")
        ]
