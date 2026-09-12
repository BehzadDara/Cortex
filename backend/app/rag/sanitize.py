import re

REDACTION = "[removed: instruction-like text]"

INJECTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(ignore|disregard|forget|override)\b[^.!?\n]{0,40}"
        r"\b(previous|prior|earlier|above|initial|original|all)\b[^.!?\n]{0,40}"
        r"\b(instruction|prompt|rule|direction)",
        r"\b(ignore|disregard|forget)\b[^.!?\n]{0,20}\b(everything|anything)\b"
        r"[^.!?\n]{0,20}\b(above|before|earlier|said|told)\b",
        r"\byou\s+are\s+now\b[^.!?\n]{0,20}\b(a|an|no\s+longer)\b",
        r"\b(reveal|repeat|print|show|output|disclose)\b[^.!?\n]{0,30}"
        r"\b(your|the)\b[^.!?\n]{0,20}\b(system\s+prompt|instructions|prompt)\b",
        r"\bnew\s+instructions?\s*:",
        r"\bdo\s+not\s+(answer|follow)\b[^.!?\n]{0,30}"
        r"\b(question|instruction|rule)",
    )
]


def looks_like_instruction(line: str) -> bool:
    return any(pattern.search(line) for pattern in INJECTION_PATTERNS)


def neutralize_instructions(text: str) -> str:
    return "\n".join(
        REDACTION if looks_like_instruction(line) else line
        for line in text.splitlines()
    )
