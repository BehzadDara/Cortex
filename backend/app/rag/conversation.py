from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import Conversation, Message
from app.rag.llm import LLMProvider
from app.rag.prompts import build_summary_prompt, build_title_prompt


def path_messages(session: Session, conversation: Conversation) -> list[Message]:
    path: list[Message] = []
    message = (
        session.get(Message, conversation.active_root_id)
        if conversation.active_root_id is not None
        else None
    )
    while message is not None:
        path.append(message)
        message = (
            session.get(Message, message.active_child_id)
            if message.active_child_id is not None
            else None
        )
    return path


def path_to(session: Session, message: Message) -> list[Message]:
    path: list[Message] = []
    node: Message | None = message
    while node is not None:
        path.append(node)
        node = session.get(Message, node.parent_id) if node.parent_id else None
    path.reverse()
    return path


def siblings_of(session: Session, message: Message) -> list[Message]:
    query = select(Message).where(Message.conversation_id == message.conversation_id)
    query = (
        query.where(Message.parent_id == message.parent_id)
        if message.parent_id is not None
        else query.where(Message.parent_id.is_(None))
    )
    return list(session.scalars(query.order_by(Message.id)))


def select_message(session: Session, message: Message) -> None:
    if message.parent_id is None:
        message.conversation.active_root_id = message.id
    else:
        parent = session.get(Message, message.parent_id)
        if parent is not None:
            parent.active_child_id = message.id


def leaf_of(session: Session, conversation: Conversation) -> Message | None:
    path = path_messages(session, conversation)
    return path[-1] if path else None


def recent_messages(path: list[Message]) -> list[Message]:
    return path[-settings.memory_recent_messages :]


def path_summary(path: list[Message]) -> tuple[str | None, int]:
    for message in reversed(path):
        if message.summary:
            return message.summary, message.summarized_depth or 0
    return None, 0


def placeholder_title(question: str) -> str:
    return question[:20]


def save_title(llm: LLMProvider, conversation_id: int, question: str) -> str | None:
    try:
        title = llm.complete(build_title_prompt(question)).strip().strip('"')[:80]
    except Exception:
        return None
    if not title:
        return None
    with SessionLocal() as session:
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            return None
        if conversation.title != placeholder_title(question):
            return None
        conversation.title = title
        session.commit()
    return title


def conversation_messages(path: list[Message]) -> list[dict]:
    messages: list[dict] = []
    summary, _ = path_summary(path)
    if summary:
        messages.append(
            {
                "role": "system",
                "content": f"Summary of earlier conversation:\n{summary}",
            }
        )
    messages.extend(
        {"role": message.role, "content": message.content}
        for message in recent_messages(path)
    )
    return messages


def history_for(session: Session, conversation: Conversation) -> list[dict]:
    return conversation_messages(path_messages(session, conversation))


def attach(session: Session, message: Message, parent_id: int | None) -> None:
    message.parent_id = parent_id
    session.add(message)
    session.flush()
    select_message(session, message)


def save_answer(
    conversation_id: int,
    parent_id: int,
    answer: str,
    steps: list[dict] | None = None,
    sources: list[dict] | None = None,
    widgets: list[dict] | None = None,
    elapsed_ms: int | None = None,
    prompt_tokens: int | None = None,
    response_tokens: int | None = None,
) -> int:
    with SessionLocal() as session:
        assistant_message = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            steps=steps or None,
            sources=sources or None,
            widgets=widgets or None,
            elapsed_ms=elapsed_ms,
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
        )
        attach(session, assistant_message, parent_id)
        session.commit()
        return assistant_message.id


def save_exchange(
    conversation_id: int,
    parent_id: int | None,
    question: str,
    answer: str,
    attachments: list[dict] | None = None,
    steps: list[dict] | None = None,
    sources: list[dict] | None = None,
    widgets: list[dict] | None = None,
    elapsed_ms: int | None = None,
    prompt_tokens: int | None = None,
    response_tokens: int | None = None,
) -> int:
    with SessionLocal() as session:
        user_message = Message(
            conversation_id=conversation_id,
            role="user",
            content=question,
            attachments=attachments or None,
        )
        attach(session, user_message, parent_id)
        assistant_message = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=answer,
            steps=steps or None,
            sources=sources or None,
            widgets=widgets or None,
            elapsed_ms=elapsed_ms,
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
        )
        attach(session, assistant_message, user_message.id)
        session.commit()
        return assistant_message.id


def save_run(
    conversation_id: int,
    parent_id: int | None,
    question: str,
    answer: str,
    **fields,
) -> int:
    with SessionLocal() as session:
        parent = session.get(Message, parent_id) if parent_id is not None else None
        regenerating = parent is not None and parent.role == "user"
    if regenerating:
        return save_answer(conversation_id, parent_id, answer, **fields)
    return save_exchange(conversation_id, parent_id, question, answer, **fields)


def summarize_if_due(conversation_id: int, llm: LLMProvider) -> None:
    with SessionLocal() as session:
        conversation = session.get(Conversation, conversation_id)
        if conversation is not None:
            maybe_summarize(session, llm, conversation)


def maybe_summarize(
    session: Session, llm: LLMProvider, conversation: Conversation
) -> None:
    path = path_messages(session, conversation)
    previous, summarized_depth = path_summary(path)
    boundary = max(len(path) - settings.memory_recent_messages, 0)
    unsummarized = path[summarized_depth:boundary]
    if len(unsummarized) < settings.memory_summary_threshold:
        return

    transcript = "\n".join(
        f"{message.role}: {message.content}" for message in unsummarized
    )
    path[boundary - 1].summary = llm.complete(
        build_summary_prompt(previous, transcript)
    )
    path[boundary - 1].summarized_depth = boundary
    session.commit()
