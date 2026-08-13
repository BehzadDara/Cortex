import hashlib
from dataclasses import dataclass
from io import BytesIO

import httpx
from PIL import Image as PilImage

from app.config import settings

USABLE_FORMATS = {"png", "jpeg", "webp"}

DOWNLOAD_TIMEOUT_SECONDS = 15


@dataclass
class ExtractedImage:
    data: bytes
    extension: str
    source_url: str | None = None


def usable_image(data: bytes, source_url: str | None = None) -> ExtractedImage | None:
    if len(data) > settings.max_image_bytes:
        return None
    try:
        with PilImage.open(BytesIO(data)) as picture:
            format_name = (picture.format or "").lower()
            width, height = picture.size
            picture.verify()
    except Exception:
        return None
    if format_name not in USABLE_FORMATS:
        return None
    if min(width, height) < settings.min_image_dimension:
        return None
    return ExtractedImage(data=data, extension=format_name, source_url=source_url)


def download_image(url: str) -> ExtractedImage | None:
    try:
        response = httpx.get(
            url, timeout=DOWNLOAD_TIMEOUT_SECONDS, follow_redirects=True
        )
        response.raise_for_status()
    except httpx.HTTPError:
        return None
    if not response.headers.get("content-type", "").startswith("image/"):
        return None
    return usable_image(response.content, source_url=url)


def deduplicate_images(images: list[ExtractedImage]) -> list[ExtractedImage]:
    seen: set[str] = set()
    unique: list[ExtractedImage] = []
    for image in images:
        digest = hashlib.sha256(image.data).hexdigest()
        if digest not in seen:
            seen.add(digest)
            unique.append(image)
    return unique
