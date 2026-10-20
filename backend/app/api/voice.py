from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile

from app.dependencies import (
    get_fast_llm_provider,
    get_reranker,
    get_speech_to_text,
    get_text_to_speech,
    get_voice_llm_provider,
)
from app.rag.speech import TextToSpeech, spoken_text
from app.rag.transcription import SpeechToText
from app.schemas import SpeakRequest, TranscriptionResponse

router = APIRouter(tags=["voice"])


@router.post("/transcribe", response_model=TranscriptionResponse)
def transcribe(
    file: UploadFile,
    speech_to_text: SpeechToText = Depends(get_speech_to_text),
) -> TranscriptionResponse:
    try:
        text = speech_to_text.transcribe(file.file.read())
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return TranscriptionResponse(text=text)


@router.post("/speak")
def speak(
    request: SpeakRequest,
    text_to_speech: TextToSpeech = Depends(get_text_to_speech),
) -> Response:
    text = spoken_text(request.text)
    if not text:
        raise HTTPException(status_code=400, detail="nothing to read aloud")
    return Response(content=text_to_speech.speak(text), media_type="audio/wav")


WARM_UP_QUERY = "warm up"


def warm_up_reranker() -> None:
    get_reranker().rerank(WARM_UP_QUERY, [WARM_UP_QUERY])


WARM_UP_STEPS: dict[str, Callable[[], None]] = {
    "speech recognition": lambda: get_speech_to_text().warm_up(),
    "speech synthesis": lambda: get_text_to_speech().warm_up(),
    "voice model": lambda: get_voice_llm_provider().warm_up(),
    "routing model": lambda: get_fast_llm_provider().warm_up(),
    "reranker": warm_up_reranker,
}


def succeeded(step: Callable[[], None]) -> bool:
    try:
        step()
    except Exception:
        return False
    return True


@router.post("/voice/warm-up")
def warm_up() -> dict:
    with ThreadPoolExecutor() as pool:
        outcomes = dict(zip(WARM_UP_STEPS, pool.map(succeeded, WARM_UP_STEPS.values())))
    failed = [name for name, ok in outcomes.items() if not ok]
    if failed:
        raise HTTPException(
            status_code=503, detail=f"Could not load the {', '.join(failed)}."
        )
    return {"ready": True}
