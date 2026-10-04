import re
import time
from collections.abc import Callable
from dataclasses import dataclass

from app.dependencies import get_page_writer
from app.models import WebPage
from app.rag.web_pages import same_document, write_page

BASE_REQUEST = (
    "A landing page for Bean There, a specialty coffee shop in Tehran: three "
    "featured drinks with prices, opening hours, and a newsletter signup form."
)

EXTERNAL_REFERENCE = re.compile(r"""(?:src|href)\s*=\s*["']?(?:https?:)?//""", re.IGNORECASE)
ROOT_BACKGROUND = re.compile(r"--bg\s*:\s*#([0-9a-f]{6}|[0-9a-f]{3})\b", re.IGNORECASE)


@dataclass
class EditCase:
    request: str
    expect: Callable[[str], bool]


def luminance(hex_color: str) -> float:
    if len(hex_color) == 3:
        hex_color = "".join(channel * 2 for channel in hex_color)
    red, green, blue = (int(hex_color[index : index + 2], 16) for index in (0, 2, 4))
    return (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255


def has_dark_background(document: str) -> bool:
    match = ROOT_BACKGROUND.search(document)
    return match is not None and luminance(match.group(1)) < 0.35


def problems(document: str) -> list[str]:
    lowered = document.lower()
    checks = {
        "no doctype": not lowered.startswith("<!doctype html"),
        "no title": "<title" not in lowered,
        "uses remote <img>": re.search(r"<img\b(?![^>]*src\s*=\s*[\"']?data:)", lowered) is not None,
        "loads external resources": EXTERNAL_REFERENCE.search(document) is not None,
    }
    return [problem for problem, failed in checks.items() if failed]


EDITS = [
    EditCase("Switch the whole page to a dark theme.", has_dark_background),
    EditCase(
        "Add a testimonials section with three customer quotes.",
        lambda document: "testimonial" in document.lower(),
    ),
    EditCase(
        "Change the main headline to: Coffee worth the trip",
        lambda document: "coffee worth the trip" in document.lower(),
    ),
    EditCase(
        "Remove the newsletter signup form entirely.",
        lambda document: "<form" not in document.lower(),
    ),
]


def timed_write(request: str, previous: WebPage | None) -> tuple[str | None, float]:
    started = time.perf_counter()
    document = write_page(get_page_writer(), request, previous)
    return document, time.perf_counter() - started


def main() -> None:
    document, elapsed = timed_write(BASE_REQUEST, None)
    if document is None:
        print(f"FAIL  {elapsed:5.1f}s  build: no HTML document returned")
        return
    issues = problems(document) + ([] if "<form" in document.lower() else ["no signup form"])
    print(f"{'FAIL' if issues else 'PASS'}  {elapsed:5.1f}s  build a self-contained page {issues or ''}")
    base = WebPage(version=1, title="base", request=BASE_REQUEST, html=document)

    passed = 0
    for case in EDITS:
        edited, elapsed = timed_write(case.request, base)
        ok = (
            edited is not None
            and not same_document(edited, base.html)
            and not problems(edited)
            and case.expect(edited)
        )
        passed += ok
        print(f"{'PASS' if ok else 'FAIL'}  {elapsed:5.1f}s  edit: {case.request}")
    print(f"edits applied: {passed}/{len(EDITS)}")


if __name__ == "__main__":
    main()
