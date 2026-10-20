import io
import random
from dataclasses import dataclass

import numpy as np
import soundfile

TARGET_RMS = 10 ** (-20 / 20)
PEAK_LIMIT = 0.95
SILENCE_LEVEL = 0.004
EDGE_PADDING_SECONDS = 0.04
FADE_SECONDS = 0.012
LEAD_IN_SECONDS = 0.6
TAIL_SECONDS = 1.2
SEGMENT_PAUSE_SECONDS = 0.95
TURN_PAUSE_SECONDS = 0.38
SAME_SPEAKER_PAUSE_SECONDS = 0.3
INTERJECTION_PAUSE_SECONDS = 0.18
INTERJECTION_SECONDS = 1.1
PAUSE_JITTER_SECONDS = 0.07


@dataclass
class Clip:
    audio: bytes
    speaker: str
    segment: int


@dataclass
class MixedEpisode:
    audio: bytes
    timings: list[tuple[int, int]]
    duration_ms: int


def decoded(audio: bytes) -> tuple[np.ndarray, int]:
    samples, rate = soundfile.read(io.BytesIO(audio), dtype="float32")
    if samples.ndim > 1:
        samples = samples.mean(axis=1)
    return samples, rate


def trimmed(samples: np.ndarray, rate: int) -> np.ndarray:
    loud = np.flatnonzero(np.abs(samples) > SILENCE_LEVEL)
    if loud.size == 0:
        return samples
    padding = int(EDGE_PADDING_SECONDS * rate)
    return samples[max(loud[0] - padding, 0) : loud[-1] + padding + 1]


def leveled(samples: np.ndarray) -> np.ndarray:
    rms = float(np.sqrt(np.mean(samples**2))) if samples.size else 0.0
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    if rms == 0 or peak == 0:
        return samples
    return samples * min(TARGET_RMS / rms, PEAK_LIMIT / peak)


def faded(samples: np.ndarray, rate: int) -> np.ndarray:
    length = min(int(FADE_SECONDS * rate), samples.size // 2)
    if length == 0:
        return samples
    ramp = np.linspace(0.0, 1.0, length, dtype=np.float32)
    samples = samples.copy()
    samples[:length] *= ramp
    samples[-length:] *= ramp[::-1]
    return samples


def pause_seconds(
    previous: Clip, clip: Clip, clip_seconds: float, rng: random.Random
) -> float:
    if clip.segment != previous.segment:
        base = SEGMENT_PAUSE_SECONDS
    elif clip.speaker == previous.speaker:
        base = SAME_SPEAKER_PAUSE_SECONDS
    elif clip_seconds < INTERJECTION_SECONDS:
        base = INTERJECTION_PAUSE_SECONDS
    else:
        base = TURN_PAUSE_SECONDS
    return max(base + rng.uniform(-PAUSE_JITTER_SECONDS, PAUSE_JITTER_SECONDS), 0.05)


def silence(seconds: float, rate: int) -> np.ndarray:
    return np.zeros(int(seconds * rate), dtype=np.float32)


def encoded_mp3(samples: np.ndarray, rate: int) -> bytes:
    buffer = io.BytesIO()
    soundfile.write(buffer, samples, rate, format="MP3")
    return buffer.getvalue()


def mix_episode(clips: list[Clip], seed: int) -> MixedEpisode:
    if not clips:
        raise ValueError("There is nothing to mix.")
    rng = random.Random(seed)
    rate = decoded(clips[0].audio)[1]
    parts = [silence(LEAD_IN_SECONDS, rate)]
    position = parts[0].size
    timings: list[tuple[int, int]] = []
    previous: Clip | None = None
    for clip in clips:
        samples, clip_rate = decoded(clip.audio)
        if clip_rate != rate:
            raise ValueError("Every clip must share one sample rate.")
        samples = faded(leveled(trimmed(samples, rate)), rate)
        if previous is not None:
            gap = silence(pause_seconds(previous, clip, samples.size / rate, rng), rate)
            parts.append(gap)
            position += gap.size
        timings.append((position * 1000 // rate, (position + samples.size) * 1000 // rate))
        parts.append(samples)
        position += samples.size
        previous = clip
    parts.append(silence(TAIL_SECONDS, rate))
    mix = np.concatenate(parts)
    return MixedEpisode(
        audio=encoded_mp3(mix, rate),
        timings=timings,
        duration_ms=mix.size * 1000 // rate,
    )
