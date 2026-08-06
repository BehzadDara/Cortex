from fastapi import APIRouter, Depends, Form, UploadFile

from app.dependencies import get_vision_provider
from app.rag.vision import VisionProvider
from app.schemas import ImageAskResponse

router = APIRouter(tags=["vision"])


@router.post("/ask-image", response_model=ImageAskResponse)
def ask_image(
    file: UploadFile,
    question: str = Form(...),
    vision: VisionProvider = Depends(get_vision_provider),
) -> ImageAskResponse:
    answer = vision.describe(file.file.read(), question)
    return ImageAskResponse(answer=answer)
