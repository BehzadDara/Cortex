import io
from typing import Protocol

import numpy as np
import soundfile

from app.config import settings

WHISPER_SAMPLE_RATE = 16000

SILENCE_RMS = 0.003

WARM_UP_SECONDS = 0.5


class SpeechToText(Protocol):
    def transcribe(self, audio: bytes) -> str: ...

    def warm_up(self) -> None: ...


class WhisperSpeechToText:
    def transcribe(self, audio: bytes) -> str:
        samples = waveform(audio)
        if is_silent(samples):
            return ""
        return self.recognize(samples)

    def warm_up(self) -> None:
        self.recognize(np.zeros(int(WHISPER_SAMPLE_RATE * WARM_UP_SECONDS), np.float32))

    def recognize(self, samples: np.ndarray) -> str:
        import mlx_whisper

        result = mlx_whisper.transcribe(samples, path_or_hf_repo=settings.stt_model)
        return result["text"].strip()


def is_silent(samples: np.ndarray) -> bool:
    if samples.size == 0:
        return True
    return float(np.sqrt(np.mean(np.square(samples)))) < SILENCE_RMS


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
