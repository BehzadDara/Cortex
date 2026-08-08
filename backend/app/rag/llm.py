import json
from collections.abc import Callable, Iterator
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

    def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict],
        on_token: Callable[[str], None],
    ) -> ChatReply: ...


class OllamaLLMProvider:
    def __init__(self, model: str | None = None, think: bool = True) -> None:
        self.model = model or settings.llm_model
        self.think = think

    def base_request(self) -> dict:
        request = {
            "model": self.model,
            "options": {"num_ctx": settings.llm_num_ctx},
        }
        if self.think:
            request["think"] = True
        return request

    def chat(self, messages: list[dict], tools: list[dict]) -> ChatReply:
        request = {
            **self.base_request(),
            "messages": messages,
            "tools": tools,
            "stream": False,
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

    def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict],
        on_token: Callable[[str], None],
    ) -> ChatReply:
        request = {
            **self.base_request(),
            "messages": messages,
            "tools": tools,
            "stream": True,
        }
        content_parts: list[str] = []
        raw_calls: list[dict] = []
        with httpx.stream(
            "POST", f"{settings.ollama_url}/api/chat", json=request, timeout=300
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                part = json.loads(line)
                message = part.get("message") or {}
                token = message.get("content", "")
                if token:
                    content_parts.append(token)
                    on_token(token)
                raw_calls.extend(message.get("tool_calls") or [])

        content = "".join(content_parts)
        raw_message: dict = {"role": "assistant", "content": content}
        if raw_calls:
            raw_message["tool_calls"] = raw_calls
        tool_calls = [
            ToolCall(
                name=call["function"]["name"],
                arguments=call["function"].get("arguments") or {},
            )
            for call in raw_calls
        ]
        return ChatReply(
            content=content, tool_calls=tool_calls, raw_message=raw_message
        )

    def complete(self, prompt: str) -> str:
        request = {**self.base_request(), "prompt": prompt, "stream": False}
        response = httpx.post(
            f"{settings.ollama_url}/api/generate", json=request, timeout=300
        )
        response.raise_for_status()
        return response.json()["response"].strip()

    def stream(self, prompt: str, usage: dict | None = None) -> Iterator[str]:
        request = {**self.base_request(), "prompt": prompt, "stream": True}
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
