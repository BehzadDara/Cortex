from dataclasses import dataclass
from typing import Protocol
from urllib.parse import quote

import httpx

from app.config import settings

GENERATION_TIMEOUT_SECONDS = 600

POLLINATIONS_URL = "https://image.pollinations.ai/prompt"


@dataclass
class GeneratedImage:
    data: bytes
    extension: str
    width: int
    height: int


class ImageGenerator(Protocol):
    def generate(self, prompt: str) -> GeneratedImage: ...


class PollinationsImageGenerator:
    def generate(self, prompt: str) -> GeneratedImage:
        response = httpx.get(
            f"{POLLINATIONS_URL}/{quote(prompt)}",
            params={
                "width": settings.image_size,
                "height": settings.image_size,
                "nologo": "true",
                "private": "true",
            },
            timeout=GENERATION_TIMEOUT_SECONDS,
            follow_redirects=True,
        )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if not content_type.startswith("image/"):
            raise RuntimeError(
                f"Pollinations returned '{content_type}' instead of an image"
            )
        extension = content_type.removeprefix("image/").split(";")[0]
        return GeneratedImage(
            data=response.content,
            extension=extension or "jpeg",
            width=settings.image_size,
            height=settings.image_size,
        )
