from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile

from app.dependencies import get_speech_to_text, get_text_to_speech
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
