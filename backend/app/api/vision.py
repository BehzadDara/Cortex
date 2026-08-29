from fastapi import APIRouter, Depends, Form, UploadFile
from sqlalchemy.orm import Session

from app.api.common import find_or_create_conversation, start_title_generation
from app.dependencies import (
    get_fast_llm_provider,
    get_llm_provider,
    get_session,
    get_vision_provider,
)
from app.rag.conversation import leaf_of, save_exchange, summarize_if_due
from app.rag.llm import LLMProvider
from app.rag.prompts import build_image_question_prompt
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

    answer = vision.describe(file.file.read(), build_image_question_prompt(question))
    leaf = leaf_of(session, conversation)
    save_exchange(
        conversation.id,
        leaf.id if leaf else None,
        f"{question} (image: {file.filename})",
        answer,
    )
    summarize_if_due(conversation.id, llm)
    return ImageAskResponse(conversation_id=conversation.id, answer=answer)
