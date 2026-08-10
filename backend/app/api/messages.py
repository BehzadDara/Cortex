from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.conversations import fallback_title, to_summary
from app.dependencies import get_session
from app.models import Conversation, Message
from app.schemas import ConversationSummary, FeedbackRequest, FeedbackResponse

router = APIRouter(prefix="/messages", tags=["messages"])


def branch_title(source: Conversation) -> str:
    return f"Branch of {source.title or fallback_title(source)}"[:80]


def copy_message(message: Message, conversation_id: int) -> Message:
    return Message(
        conversation_id=conversation_id,
        role=message.role,
        content=message.content,
        steps=message.steps,
        sources=message.sources,
        widgets=message.widgets,
        elapsed_ms=message.elapsed_ms,
        prompt_tokens=message.prompt_tokens,
        response_tokens=message.response_tokens,
    )


@router.put("/{message_id}/feedback", response_model=FeedbackResponse)
def set_feedback(
    message_id: int,
    request: FeedbackRequest,
    session: Session = Depends(get_session),
) -> FeedbackResponse:
    message = session.get(Message, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found")
    if message.role != "assistant":
        raise HTTPException(
            status_code=400, detail="Only assistant messages accept feedback"
        )

    message.feedback = request.value
    session.commit()
    return FeedbackResponse(id=message_id, feedback=message.feedback)


@router.post("/{message_id}/branch", response_model=ConversationSummary)
def branch_conversation(
    message_id: int, session: Session = Depends(get_session)
) -> ConversationSummary:
    message = session.get(Message, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found")
    if message.role != "assistant":
        raise HTTPException(
            status_code=400, detail="Branch from an assistant message"
        )

    source = message.conversation
    copied = [entry for entry in source.messages if entry.id <= message.id]
    branch = Conversation(
        title=branch_title(source),
        branched_from_id=source.id,
        branched_count=len(copied),
    )
    if source.summarized_count <= len(copied):
        branch.summary = source.summary
        branch.summarized_count = source.summarized_count
    session.add(branch)
    session.flush()
    session.add_all(copy_message(entry, branch.id) for entry in copied)
    session.commit()
    return to_summary(branch)
