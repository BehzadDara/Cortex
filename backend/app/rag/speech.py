import io
import re
import wave
from typing import Protocol

import soundfile

from app.config import settings
from app.rag.language import is_persian


WARM_UP_TEXT = "Ready."


class TextToSpeech(Protocol):
    def speak(self, text: str) -> bytes: ...

    def warm_up(self) -> None: ...


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

    def warm_up(self) -> None:
        self.speak(WARM_UP_TEXT)


class PiperTextToSpeech:
    def __init__(self, model_path: str) -> None:
        from piper import PiperVoice

        self.voice = PiperVoice.load(model_path)

    def speak(self, text: str) -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            self.voice.synthesize_wav(text, wav_file)
        return buffer.getvalue()

    def warm_up(self) -> None:
        self.speak(WARM_UP_TEXT)


class BilingualTextToSpeech:
    def __init__(self, english: TextToSpeech, persian: TextToSpeech) -> None:
        self.english = english
        self.persian = persian

    def speak(self, text: str) -> bytes:
        voice = self.persian if is_persian(text) else self.english
        return voice.speak(text)

    def warm_up(self) -> None:
        self.english.warm_up()
        self.persian.warm_up()


CODE_BLOCK = re.compile(r"```.*?(```|$)", re.DOTALL)
TABLE_ROW = re.compile(r"^[ \t]*\|.*$", re.MULTILINE)
IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
LINK = re.compile(r"\[([^\]]+)\]\(([^)]*)\)")
CITATION_MARKER = re.compile(r"\s*\[\d+\](?!\()")
INLINE_CODE = re.compile(r"`([^`]*)`")
MARKDOWN_SYMBOLS = re.compile(r"[*_#>|~]")
EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\u2300-\u23FF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D]"
)
THOUSANDS_SEPARATOR = re.compile(r"(?<=\d),(?=\d{3}\b)")
DOLLARS = re.compile(r"\$(\d+)(?:\.(\d{1,2}))?")
CLOCK_TIME = re.compile(r"\b(\d{1,2}):(\d{2})\b(?=(\s*[ap]\.?m\b)?)", re.IGNORECASE)
DECIMAL = re.compile(r"\b(\d+)\.(\d+)\b")
PERSIAN_DIGIT_GROUP = re.compile(r"(\d+)[٫.,](?=\d{3}(?!\d))")
PERSIAN_DECIMAL_SEPARATOR = re.compile(r"(?<=\d)٫(?=\d)")
PERSIAN_CLOCK_TIME = re.compile(r"(\d{1,2}):(\d{2})")
PERSIAN_UNITS = [
    (re.compile(r"\s?°\s?C\b"), " درجه سانتی‌گراد"),
    (re.compile(r"\s?°\s?F\b"), " درجه فارنهایت"),
    (re.compile(r"\s?°"), " درجه"),
    (re.compile(r"\bkm/h\b"), " کیلومتر بر ساعت"),
]
UNITS = [
    (re.compile(r"\s?°\s?C\b"), " degrees Celsius"),
    (re.compile(r"\s?°\s?F\b"), " degrees Fahrenheit"),
    (re.compile(r"\s?°"), " degrees"),
    (re.compile(r"\bkm/h\b"), " kilometers per hour"),
    (re.compile(r"\bm/s\b"), " meters per second"),
    (re.compile(r"\bmph\b"), " miles per hour"),
]


def spoken_text(markdown: str) -> str:
    text = CODE_BLOCK.sub(" ", markdown)
    text = TABLE_ROW.sub(" ", text)
    text = IMAGE.sub(" ", text)
    text = LINK.sub(r"\1", text)
    text = CITATION_MARKER.sub("", text)
    text = INLINE_CODE.sub(r"\1", text)
    text = MARKDOWN_SYMBOLS.sub(" ", text)
    text = EMOJI.sub("", text)
    if is_persian(text):
        text = spoken_persian_numbers(text)
    else:
        text = spoken_numbers(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" ([.,!?;:])", r"\1", text)
    return re.sub(r"\s*\n\s*", "\n", text).strip()


def spoken_numbers(text: str) -> str:
    text = THOUSANDS_SEPARATOR.sub("", text)
    text = DOLLARS.sub(spoken_dollars, text)
    text = CLOCK_TIME.sub(spoken_clock_time, text)
    text = DECIMAL.sub(spoken_decimal, text)
    for unit, words in UNITS:
        text = unit.sub(words, text)
    return text


def spoken_persian_numbers(text: str) -> str:
    text = PERSIAN_DIGIT_GROUP.sub(joined_digit_group, text)
    text = PERSIAN_DECIMAL_SEPARATOR.sub(" ممیز ", text)
    text = PERSIAN_CLOCK_TIME.sub(r"\1 و \2", text)
    for unit, words in PERSIAN_UNITS:
        text = unit.sub(words, text)
    return text


def joined_digit_group(match: re.Match) -> str:
    whole = match.group(1)
    return whole if int(whole) > 0 else match.group(0)


def spoken_dollars(match: re.Match) -> str:
    dollars, cents = match.group(1), int(match.group(2) or 0)
    spoken = f"{dollars} {'dollar' if dollars == '1' else 'dollars'}"
    return f"{spoken} and {cents} cents" if cents else spoken


def spoken_clock_time(match: re.Match) -> str:
    hours, minutes, meridiem = match.groups()
    if minutes == "00":
        return hours if meridiem else f"{hours} o'clock"
    if minutes.startswith("0"):
        return f"{hours} oh {minutes[1]}"
    return f"{hours} {minutes}"


def spoken_decimal(match: re.Match) -> str:
    whole, fraction = match.groups()
    return f"{whole} point {' '.join(fraction)}"
