import re

PERSIAN_LETTER = re.compile(r"[\u0600-\u06FF]")
LATIN_LETTER = re.compile(r"[A-Za-z]")


def is_persian(text: str) -> bool:
    return len(PERSIAN_LETTER.findall(text)) > len(LATIN_LETTER.findall(text))
