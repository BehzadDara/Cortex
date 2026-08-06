from dataclasses import dataclass
from urllib.parse import urldefrag, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

BOILERPLATE_TAGS = ["script", "style", "nav", "footer", "header", "aside"]


@dataclass
class CrawledPage:
    url: str
    text: str


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
            pages.append(CrawledPage(url=url, text=text))

        for link in links:
            if urlparse(link).netloc == domain and link not in visited:
                queue.append(link)

    return pages
