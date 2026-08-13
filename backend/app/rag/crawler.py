from dataclasses import dataclass
from urllib.parse import urldefrag, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.rag.images import ExtractedImage, download_image

BOILERPLATE_TAGS = ["script", "style", "nav", "footer", "header", "aside"]


@dataclass
class CrawledPage:
    url: str
    text: str
    images: list[ExtractedImage]


def normalize_url(url: str) -> str:
    without_fragment, _ = urldefrag(url)
    return without_fragment.rstrip("/")


def extract_text(soup: BeautifulSoup) -> str:
    for tag in soup(BOILERPLATE_TAGS):
        tag.decompose()
    lines = (line.strip() for line in soup.get_text("\n").splitlines())
    return "\n".join(line for line in lines if line)


def extract_links(soup: BeautifulSoup, base_url: str) -> list[str]:
    links = (
        urljoin(base_url, anchor["href"]) for anchor in soup.find_all("a", href=True)
    )
    return [normalize_url(link) for link in links if link.startswith("http")]


def extract_image_urls(soup: BeautifulSoup, base_url: str) -> list[str]:
    urls: list[str] = []
    for tag in soup.find_all("img", src=True):
        url = urljoin(base_url, tag["src"])
        if url.startswith("http") and url not in urls:
            urls.append(url)
    return urls


def fetch_images(soup: BeautifulSoup, base_url: str) -> list[ExtractedImage]:
    images: list[ExtractedImage] = []
    for url in extract_image_urls(soup, base_url):
        if len(images) >= settings.crawl_max_images_per_page:
            break
        image = download_image(url)
        if image is not None:
            images.append(image)
    return images


def fetch_html(url: str) -> str | None:
    try:
        response = httpx.get(url, timeout=15, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError:
        return None
    if "text/html" not in response.headers.get("content-type", ""):
        return None
    return response.text


def crawl(start_url: str, max_pages: int) -> list[CrawledPage]:
    start = normalize_url(start_url)
    domain = urlparse(start).netloc
    queue = [start]
    visited: set[str] = set()
    pages: list[CrawledPage] = []

    while queue and len(pages) < max_pages:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        html = fetch_html(url)
        if html is None:
            continue

        soup = BeautifulSoup(html, "html.parser")
        links = extract_links(soup, url)
        text = extract_text(soup)
        if text:
            pages.append(
                CrawledPage(url=url, text=text, images=fetch_images(soup, url))
            )

        for link in links:
            if urlparse(link).netloc == domain and link not in visited:
                queue.append(link)

    return pages
