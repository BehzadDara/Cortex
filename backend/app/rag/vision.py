import base64
import re
from typing import Protocol

import httpx

from app.config import settings

GEMMA_CONTROL_TOKENS = re.compile(
    r"<(?:start_of_image|end_of_image|image_soft_token|start_of_turn|end_of_turn|bos|eos|pad)>[ \t]*"
)


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
        return GEMMA_CONTROL_TOKENS.sub("", response.json()["response"]).strip()
