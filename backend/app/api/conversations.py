from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import get_session
from app.models import Conversation
from app.schemas import ConversationResponse, MessageResponse

router = APIRouter(prefix="/conversations", tags=["conversations"])


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
