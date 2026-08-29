from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, object_session

from app.dependencies import get_session
from app.models import Conversation, Message
from app.rag.conversation import path_messages, siblings_of
from app.schemas import (
    ConversationRename,
    ConversationResponse,
    ConversationSummary,
    MessageResponse,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


def fallback_title(conversation: Conversation) -> str:
    first_user = next(
        (message for message in conversation.messages if message.role == "user"), None
    )
    return first_user.content if first_user else "New chat"


def to_message_response(session: Session, message: Message) -> MessageResponse:
    siblings = siblings_of(session, message)
    return MessageResponse(
        id=message.id,
        role=message.role,
        content=message.content,
        attachments=message.attachments,
        parent_id=message.parent_id,
        variant_index=siblings.index(message) + 1,
        variant_count=len(siblings),
        variant_ids=[sibling.id for sibling in siblings],
        steps=message.steps,
        sources=message.sources,
        widgets=message.widgets,
        feedback=message.feedback,
        elapsed_ms=message.elapsed_ms,
        prompt_tokens=message.prompt_tokens,
        response_tokens=message.response_tokens,
    )


def to_summary(conversation: Conversation) -> ConversationSummary:
    title = conversation.title or fallback_title(conversation)
    session = object_session(conversation)
    return ConversationSummary(
        id=conversation.id,
        title=title[:80],
        message_count=len(path_messages(session, conversation)),
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


@router.patch("/{conversation_id}", response_model=ConversationSummary)
def rename_conversation(
    conversation_id: int,
    request: ConversationRename,
    session: Session = Depends(get_session),
) -> ConversationSummary:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    conversation.title = request.title.strip()[:80]
    session.commit()
    return to_summary(conversation)


@router.delete("/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: int, session: Session = Depends(get_session)
) -> None:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    session.delete(conversation)
    session.commit()


@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: int, session: Session = Depends(get_session)
) -> ConversationResponse:
    conversation = session.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    source = (
        session.get(Conversation, conversation.branched_from_id)
        if conversation.branched_from_id is not None
        else None
    )
    return ConversationResponse(
        id=conversation.id,
        active_thread=conversation.active_thread,
        branched_from_id=conversation.branched_from_id,
        branched_from_title=(
            (source.title or fallback_title(source)) if source else None
        ),
        branched_count=conversation.branched_count,
        messages=[
            to_message_response(session, message)
            for message in path_messages(session, conversation)
        ],
    )
