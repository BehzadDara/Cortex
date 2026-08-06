from fastapi import APIRouter, Depends, Form, UploadFile
from sqlalchemy.orm import Session

from app.api.common import find_or_create_conversation, start_title_generation
from app.dependencies import (
    get_fast_llm_provider,
    get_llm_provider,
    get_session,
    get_vision_provider,
)
from app.rag.conversation import save_exchange
from app.rag.llm import LLMProvider
from app.rag.vision import VisionProvider
from app.schemas import ImageAskResponse

router = APIRouter(tags=["vision"])


@router.post("/ask-image", response_model=ImageAskResponse)
def ask_image(
    file: UploadFile,
    question: str = Form(...),
    conversation_id: int | None = Form(None),
    session: Session = Depends(get_session),
    vision: VisionProvider = Depends(get_vision_provider),
    llm: LLMProvider = Depends(get_llm_provider),
    fast_llm: LLMProvider = Depends(get_fast_llm_provider),
) -> ImageAskResponse:
    conversation, is_new = find_or_create_conversation(
        session, conversation_id, question
    )
    if is_new:
        start_title_generation(fast_llm, conversation.id, question, {})

    answer = vision.describe(file.file.read(), question)
    save_exchange(
        conversation.id, f"{question} (image: {file.filename})", answer, llm
    )
    return ImageAskResponse(conversation_id=conversation.id, answer=answer)
