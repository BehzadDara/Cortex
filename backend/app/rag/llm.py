import json
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.config import settings
from app.tracing import describe_run, record_token_usage, traced


@dataclass
class ToolCall:
    name: str
    arguments: dict


@dataclass
class ChatReply:
    content: str
    tool_calls: list[ToolCall]
    raw_message: dict
    prompt_tokens: int = 0
    response_tokens: int = 0


class LLMProvider(Protocol):
    def stream(self, prompt: str, usage: dict | None = None) -> Iterator[str]: ...

    def complete(self, prompt: str) -> str: ...

    def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict],
        on_token: Callable[[str], None],
    ) -> ChatReply:         ...


def chat_completion(reply: ChatReply) -> dict:
    return {"choices": [{"message": reply.raw_message}]}


def joined_text(tokens: list[str]) -> str:
    return "".join(tokens)


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

    def describe_call(self) -> None:
        describe_run(ls_provider="ollama", ls_model_name=self.model)

    @traced(
        "Ollama chat",
        run_type="llm",
        hidden_inputs=("on_token",),
        format_output=chat_completion,
    )
    def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict],
        on_token: Callable[[str], None],
    ) -> ChatReply:
        self.describe_call()
        request = {
            **self.base_request(),
            "messages": messages,
            "tools": tools,
            "stream": True,
        }
        content_parts: list[str] = []
        raw_calls: list[dict] = []
        prompt_tokens = 0
        response_tokens = 0
        with httpx.stream(
            "POST", f"{settings.ollama_url}/api/chat", json=request, timeout=300
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                part = json.loads(line)
                if part.get("done"):
                    prompt_tokens = part.get("prompt_eval_count") or 0
                    response_tokens = part.get("eval_count") or 0
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
        record_token_usage(prompt_tokens, response_tokens)
        return ChatReply(
            content=content,
            tool_calls=tool_calls,
            raw_message=raw_message,
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
        )

    @traced("Ollama complete", run_type="llm")
    def complete(self, prompt: str) -> str:
        self.describe_call()
        request = {**self.base_request(), "prompt": prompt, "stream": False}
        request["options"] = {**request["options"], "temperature": 0}
        response = httpx.post(
            f"{settings.ollama_url}/api/generate", json=request, timeout=300
        )
        response.raise_for_status()
        result = response.json()
        record_token_usage(
            result.get("prompt_eval_count") or 0, result.get("eval_count") or 0
        )
        return result["response"].strip()

    @traced(
        "Ollama stream",
        run_type="llm",
        hidden_inputs=("usage",),
        reduce_stream=joined_text,
    )
    def stream(self, prompt: str, usage: dict | None = None) -> Iterator[str]:
        self.describe_call()
        request = {**self.base_request(), "prompt": prompt, "stream": True}
        with httpx.stream(
            "POST", f"{settings.ollama_url}/api/generate", json=request, timeout=300
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                part = json.loads(line)
                if part.get("done"):
                    record_token_usage(
                        part.get("prompt_eval_count") or 0, part.get("eval_count") or 0
                    )
                    if usage is not None:
                        usage["prompt_tokens"] = part.get("prompt_eval_count")
                        usage["response_tokens"] = part.get("eval_count")
                token = part.get("response", "")
                if token:
                    yield token
