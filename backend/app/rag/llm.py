import json
from collections.abc import Iterator
from typing import Protocol

import httpx

from app.config import settings


class LLMProvider(Protocol):
    def stream(self, prompt: str) -> Iterator[str]: ...


class OllamaLLMProvider:
    def stream(self, prompt: str) -> Iterator[str]:
        request = {
            "model": settings.llm_model,
            "prompt": prompt,
            "stream": True,
            "think": True,
        }
        with httpx.stream(
            "POST", f"{settings.ollama_url}/api/generate", json=request, timeout=300
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                part = json.loads(line)
                token = part.get("response", "")
                if token:
                    yield token
