from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import get_session
from app.models import Message
from app.schemas import FeedbackRequest, FeedbackResponse

router = APIRouter(prefix="/messages", tags=["messages"])


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
