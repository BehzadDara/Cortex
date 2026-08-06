import base64
from typing import Protocol

import httpx

from app.config import settings


class VisionProvider(Protocol):
    def describe(self, image: bytes, prompt: str) -> str: ...


class OllamaVisionProvider:
    def describe(self, image: bytes, prompt: str) -> str:
        request = {
            "model": settings.vision_model,
            "prompt": prompt,
            "images": [base64.b64encode(image).decode()],
            "stream": False,
            "options": {"num_ctx": settings.llm_num_ctx},
        }
        response = httpx.post(
            f"{settings.ollama_url}/api/generate", json=request, timeout=300
        )
        response.raise_for_status()
        return response.json()["response"].strip()
