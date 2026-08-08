import json
import threading

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Conversation
from app.rag.conversation import placeholder_title, save_title
from app.rag.llm import LLMProvider


def sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def title_event(conversation_id: int, title_holder: dict | None) -> str | None:
    if title_holder is None or "title" not in title_holder:
        return None
    title = title_holder.pop("title")
    return sse_event({"type": "title", "id": conversation_id, "title": title})


def find_or_create_conversation(
    session: Session, conversation_id: int | None, question: str
) -> tuple[Conversation, bool]:
    if conversation_id is not None:
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conversation, False

    conversation = Conversation(title=placeholder_title(question))
    session.add(conversation)
    session.commit()
    return conversation, True


def start_title_generation(
    llm: LLMProvider, conversation_id: int, question: str, holder: dict
) -> None:
    def work() -> None:
        title = save_title(llm, conversation_id, question)
        if title:
            holder["title"] = title

    threading.Thread(target=work, daemon=True).start()
