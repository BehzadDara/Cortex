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


def tool_result_groups(messages: list[dict]) -> list[list[dict]]:
    groups: list[list[dict]] = []
    for message in messages:
        if message.get("role") == "tool" and groups:
            groups[-1].append(message)
        else:
            groups.append([message])
    return groups


def last_question(groups: list[list[dict]]) -> int | None:
    return next(
        (
            index
            for index in reversed(range(len(groups)))
            if groups[index][0].get("role") == "user"
        ),
        None,
    )


def undroppable(groups: list[list[dict]]) -> set[int]:
    if not groups:
        return set()
    kept = {len(groups) - 1}
    question = last_question(groups)
    if question is not None:
        kept.add(question)
    return kept


def kept_indices(messages: list[dict], reserved: int = 0) -> list[int]:
    budget = prompt_budget() - reserved
    head = leading_system(messages)
    groups = tool_result_groups(messages[len(head) :])
    kept = undroppable(groups)
    used = estimate_messages(head) + sum(
        estimate_messages(groups[index]) for index in kept
    )
    for index in reversed(range(len(groups))):
        if index in kept:
            continue
        cost = estimate_messages(groups[index])
        if used + cost > budget:
            break
        used += cost
        kept.add(index)
    offsets = list(range(len(head)))
    position = len(head)
    for index, group in enumerate(groups):
        if index in kept:
            offsets.extend(range(position, position + len(group)))
        position += len(group)
    return offsets


def within_budget(messages: list[dict], reserved: int = 0) -> list[dict]:
    return [messages[index] for index in kept_indices(messages, reserved)]
