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
        text, language = self.recognize(samples)
        if language in settings.stt_languages:
            return text
        text, _ = self.recognize(samples, likeliest_language(samples))
        return text

    def warm_up(self) -> None:
        self.recognize(np.zeros(int(WHISPER_SAMPLE_RATE * WARM_UP_SECONDS), np.float32))

    def recognize(
        self, samples: np.ndarray, language: str | None = None
    ) -> tuple[str, str]:
        import mlx_whisper

        result = mlx_whisper.transcribe(
            samples, path_or_hf_repo=settings.stt_model, language=language
        )
        return result["text"].strip(), result["language"]


def likeliest_language(samples: np.ndarray) -> str:
    import mlx.core as mx
    from mlx_whisper.audio import N_FRAMES, N_SAMPLES, log_mel_spectrogram, pad_or_trim
    from mlx_whisper.transcribe import ModelHolder

    model = ModelHolder.get_model(settings.stt_model, mx.float16)
    mel = log_mel_spectrogram(samples, n_mels=model.dims.n_mels, padding=N_SAMPLES)
    segment = pad_or_trim(mel, N_FRAMES, axis=-2).astype(mx.float16)
    _, probabilities = model.detect_language(segment)
    return max(settings.stt_languages, key=lambda code: probabilities.get(code, 0.0))


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
