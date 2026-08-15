import io
from typing import Protocol

import numpy as np
import soundfile

from app.config import settings

WHISPER_SAMPLE_RATE = 16000


class SpeechToText(Protocol):
    def transcribe(self, audio: bytes) -> str: ...


class WhisperSpeechToText:
    def transcribe(self, audio: bytes) -> str:
        import mlx_whisper

        samples = waveform(audio)
        if samples.size == 0:
            return ""
        result = mlx_whisper.transcribe(samples, path_or_hf_repo=settings.stt_model)
        return result["text"].strip()


def waveform(audio: bytes) -> np.ndarray:
    try:
        samples, sample_rate = soundfile.read(io.BytesIO(audio), dtype="float32")
    except soundfile.LibsndfileError as error:
        raise ValueError("unreadable audio") from error
    if samples.ndim > 1:
        samples = samples.mean(axis=1)
    if sample_rate != WHISPER_SAMPLE_RATE:
        samples = resample(samples, sample_rate, WHISPER_SAMPLE_RATE)
    return samples.astype(np.float32)


def resample(samples: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    target_length = round(len(samples) * target_rate / source_rate)
    positions = np.linspace(0, len(samples) - 1, target_length)
    return np.interp(positions, np.arange(len(samples)), samples)
