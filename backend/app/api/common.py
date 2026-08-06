import threading

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Conversation
from app.rag.conversation import save_title
from app.rag.llm import LLMProvider


def find_or_create_conversation(
    session: Session, conversation_id: int | None
) -> tuple[Conversation, bool]:
    if conversation_id is not None:
        conversation = session.get(Conversation, conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conversation, False

    conversation = Conversation()
    session.add(conversation)
    session.commit()
    return conversation, True


def start_title_generation(
    llm: LLMProvider, conversation_id: int, question: str
) -> None:
    threading.Thread(
        target=save_title, args=(llm, conversation_id, question), daemon=True
    ).start()
