import io
import re
from typing import Protocol

import soundfile

from app.config import settings


class TextToSpeech(Protocol):
    def speak(self, text: str) -> bytes: ...


class KokoroTextToSpeech:
    def __init__(self) -> None:
        from kokoro_onnx import Kokoro

        self.model = Kokoro(settings.tts_model_path, settings.tts_voices_path)

    def speak(self, text: str) -> bytes:
        samples, sample_rate = self.model.create(
            text, voice=settings.tts_voice, speed=settings.tts_speed
        )
        buffer = io.BytesIO()
        soundfile.write(buffer, samples, sample_rate, format="WAV", subtype="PCM_16")
        return buffer.getvalue()


CODE_BLOCK = re.compile(r"```.*?(```|$)", re.DOTALL)
IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
LINK = re.compile(r"\[([^\]]+)\]\(([^)]*)\)")
CITATION_MARKER = re.compile(r"\s*\[\d+\](?!\()")
INLINE_CODE = re.compile(r"`([^`]*)`")
MARKDOWN_SYMBOLS = re.compile(r"[*_#>|~]")


def spoken_text(markdown: str) -> str:
    text = CODE_BLOCK.sub(" ", markdown)
    text = IMAGE.sub(" ", text)
    text = LINK.sub(r"\1", text)
    text = CITATION_MARKER.sub("", text)
    text = INLINE_CODE.sub(r"\1", text)
    text = MARKDOWN_SYMBOLS.sub(" ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ([.,!?;:])", r"\1", text)
    return re.sub(r"\s*\n\s*", "\n", text).strip()
