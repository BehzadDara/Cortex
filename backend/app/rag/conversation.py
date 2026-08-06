from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import Conversation, Message
from app.rag.llm import LLMProvider
from app.rag.prompts import (
    build_rewrite_prompt,
    build_summary_prompt,
    build_title_prompt,
)


def recent_messages(conversation: Conversation) -> list[Message]:
    return conversation.messages[-settings.memory_recent_messages :]


def format_history(conversation: Conversation, messages: list[Message]) -> str:
    parts = []
    if conversation.summary:
        parts.append(f"Summary of earlier conversation:\n{conversation.summary}")
    parts.extend(f"{message.role}: {message.content}" for message in messages)
    return "\n".join(parts)


def save_title(llm: LLMProvider, conversation_id: int, question: str) -> None:
    try:
        title = llm.complete(build_title_prompt(question)).strip().strip('"')[:80]
    except Exception:
        return
    if not title:
        return
    with SessionLocal() as session:
        conversation = session.get(Conversation, conversation_id)
        if conversation is not None and conversation.title is None:
            conversation.title = title
            session.commit()


def rewrite_question(llm: LLMProvider, history: str, question: str) -> str:
    rewritten = llm.complete(build_rewrite_prompt(history, question))
    return rewritten or question


def maybe_summarize(
    session: Session, llm: LLMProvider, conversation: Conversation
) -> None:
    boundary = max(len(conversation.messages) - settings.memory_recent_messages, 0)
    unsummarized = conversation.messages[conversation.summarized_count : boundary]
    if len(unsummarized) < settings.memory_summary_threshold:
        return

    transcript = "\n".join(
        f"{message.role}: {message.content}" for message in unsummarized
    )
    conversation.summary = llm.complete(
        build_summary_prompt(conversation.summary, transcript)
    )
    conversation.summarized_count += len(unsummarized)
    session.commit()
