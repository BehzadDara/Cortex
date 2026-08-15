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


@dataclass
class WebVideo:
    title: str
    page_url: str
    embed_url: str | None
    thumbnail_url: str | None
    duration: str | None
    channel: str | None


class VideoSearchProvider(Protocol):
    def search(self, query: str) -> list[WebVideo]: ...


def video_thumbnail(hit: dict) -> str | None:
    images = hit.get("images") or {}
    return images.get("large") or images.get("medium") or images.get("small")


class DdgsVideoSearch:
    def search(self, query: str) -> list[WebVideo]:
        from ddgs import DDGS

        with DDGS() as client:
            hits = client.videos(query, max_results=settings.web_video_results)
        return [
            WebVideo(
                title=hit.get("title") or query,
                page_url=hit["content"],
                embed_url=hit.get("embed_url") or None,
                thumbnail_url=video_thumbnail(hit),
                duration=hit.get("duration") or None,
                channel=hit.get("uploader") or hit.get("publisher") or None,
            )
            for hit in hits
            if hit.get("content")
        ]
