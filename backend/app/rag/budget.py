from app.config import settings

BYTES_PER_TOKEN = 3


def estimate_tokens(text: str) -> int:
    return len(text.encode()) // BYTES_PER_TOKEN + 1


def estimate_message(message: dict) -> int:
    parts = [message.get("content") or ""]
    parts.extend(str(call.get("function", "")) for call in message.get("tool_calls") or [])
    return sum(estimate_tokens(part) for part in parts)


def estimate_messages(messages: list[dict]) -> int:
    return sum(estimate_message(message) for message in messages)


def prompt_budget() -> int:
    return settings.llm_num_ctx - settings.llm_response_tokens


def leading_system(messages: list[dict]) -> list[dict]:
    kept: list[dict] = []
    for message in messages:
        if message.get("role") != "system":
            break
        kept.append(message)
    return kept


def within_budget(messages: list[dict], reserved: int = 0) -> list[dict]:
    budget = prompt_budget() - reserved
    head = leading_system(messages)
    used = estimate_messages(head)
    tail: list[dict] = []
    for message in reversed(messages[len(head) :]):
        cost = estimate_message(message)
        if tail and used + cost > budget:
            break
        used += cost
        tail.append(message)
    tail.reverse()
    return head + tail
