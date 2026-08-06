import json
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.config import settings


@dataclass
class ToolCall:
    name: str
    arguments: dict


@dataclass
class ChatReply:
    content: str
    tool_calls: list[ToolCall]
    raw_message: dict


class LLMProvider(Protocol):
    def stream(self, prompt: str, usage: dict | None = None) -> Iterator[str]: ...

    def complete(self, prompt: str) -> str: ...

    def chat(self, messages: list[dict], tools: list[dict]) -> ChatReply: ...


class OllamaLLMProvider:
    def chat(self, messages: list[dict], tools: list[dict]) -> ChatReply:
        request = {
            "model": settings.llm_model,
            "messages": messages,
            "tools": tools,
            "stream": False,
            "think": True,
            "options": {"num_ctx": settings.llm_num_ctx},
        }
        response = httpx.post(
            f"{settings.ollama_url}/api/chat", json=request, timeout=300
        )
        response.raise_for_status()
        message = response.json()["message"]
        tool_calls = [
            ToolCall(
                name=call["function"]["name"],
                arguments=call["function"].get("arguments") or {},
            )
            for call in message.get("tool_calls") or []
        ]
        return ChatReply(
            content=message.get("content", ""),
            tool_calls=tool_calls,
            raw_message=message,
        )

    def complete(self, prompt: str) -> str:
        request = {
            "model": settings.llm_model,
            "prompt": prompt,
            "stream": False,
            "think": True,
            "options": {"num_ctx": settings.llm_num_ctx},
        }
        response = httpx.post(
            f"{settings.ollama_url}/api/generate", json=request, timeout=300
        )
        response.raise_for_status()
        return response.json()["response"].strip()

    def stream(self, prompt: str, usage: dict | None = None) -> Iterator[str]:
        request = {
            "model": settings.llm_model,
            "prompt": prompt,
            "stream": True,
            "think": True,
            "options": {"num_ctx": settings.llm_num_ctx},
        }
        with httpx.stream(
            "POST", f"{settings.ollama_url}/api/generate", json=request, timeout=300
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                part = json.loads(line)
                if part.get("done") and usage is not None:
                    usage["prompt_tokens"] = part.get("prompt_eval_count")
                    usage["response_tokens"] = part.get("eval_count")
                token = part.get("response", "")
                if token:
                    yield token
