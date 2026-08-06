from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dependencies import get_session
from app.models import Conversation
from app.schemas import ConversationResponse, ConversationSummary, MessageResponse

router = APIRouter(prefix="/conversations", tags=["conversations"])


def to_summary(conversation: Conversation) -> ConversationSummary:
    first_user = next(
        (message for message in conversation.messages if message.role == "user"), None
    )
    title = first_user.content if first_user else "Empty conversation"
    return ConversationSummary(
        id=conversation.id,
        title=title[:80],
        message_count=len(conversation.messages),
        created_at=conversation.created_at,
    )


@router.get("", response_model=list[ConversationSummary])
def list_conversations(
    session: Session = Depends(get_session),
) -> list[ConversationSummary]:
    conversations = session.scalars(
        select(Conversation).order_by(Conversation.id.desc())
    ).all()
    return [to_summary(conversation) for conversation in conversations]


@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: int, session: Session = Depends(get_session)
) -> ConversationResponse:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return ConversationResponse(
        id=conversation.id,
        summary=conversation.summary,
        messages=[
            MessageResponse(role=message.role, content=message.content)
            for message in conversation.messages
        ],
    )
