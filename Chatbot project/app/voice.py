"""Asking by voice: check the recording, turn it into text, fix spelled-out error codes, and hand the text to the normal question path.

The transcript is only a typed question that someone else wrote down, so it gets every check a typed question gets (length, safety,
guards). Nothing is kept: the recording lives in memory for one request. Every check here is plain code; only the speech-to-text step
is a model.
"""
import array
import io
import re
from functools import lru_cache
import wave

from app.calllog import log_call
from app.config import AUDIO_MAX_BYTES, AUDIO_MAX_SECONDS, SILENCE_LEVEL, STT_PRICE_PER_MINUTE
from app.llm import call_stt

MSG_NOTHING_HEARD = "I could not hear a question in that recording. Please try again, a little closer to the microphone."
MSG_TOO_LONG = f"That recording is longer than {AUDIO_MAX_SECONDS} seconds. Please ask a shorter question."
MSG_BAD_FILE = "That does not look like an audio recording I can read. Use a WAV, MP3, OGG, WebM, M4A or FLAC file."


class VoiceError(ValueError):
    """The recording cannot be used. The message is friendly and safe to show."""


def audio_format(data: bytes) -> str | None:
    """The kind of audio in these bytes ("wav", "mp3", ...) judged by the content, never by the file name. None if unknown."""
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "wav"
    if data[:3] == b"ID3" or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "mp3"
    if data[:4] == b"OggS":
        return "ogg"
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return "webm"
    if data[4:8] == b"ftyp":
        return "m4a"
    if data[:4] == b"fLaC":
        return "flac"
    return None


def wav_facts(data: bytes) -> dict:
    """Length in seconds and the loudest sample of a 16-bit WAV. Raises VoiceError for a damaged one."""
    try:
        with wave.open(io.BytesIO(data)) as w:
            rate, frames, width = w.getframerate(), w.getnframes(), w.getsampwidth()
            raw = w.readframes(frames)
    except (wave.Error, EOFError) as err:
        raise VoiceError(MSG_BAD_FILE) from err
    if rate <= 0:
        raise VoiceError(MSG_BAD_FILE)
    peak = 0
    if width == 2 and raw:
        samples = array.array("h", raw[: len(raw) // 2 * 2])
        peak = max(max(samples), -min(samples))
    return {"seconds": frames / rate, "peak": peak, "known_peak": width == 2}


def check_recording(data: bytes) -> dict:
    """Check a recording before anything is sent. Returns {format, seconds (None if unknown), cost_usd}. Raises VoiceError."""
    if not data:
        raise VoiceError(MSG_NOTHING_HEARD)
    if len(data) > AUDIO_MAX_BYTES:
        raise VoiceError(MSG_TOO_LONG)
    kind = audio_format(data)
    if kind is None:
        raise VoiceError(MSG_BAD_FILE)
    seconds = None
    if kind == "wav":
        facts = wav_facts(data)
        seconds = facts["seconds"]
        if seconds > AUDIO_MAX_SECONDS:
            raise VoiceError(MSG_TOO_LONG)
        if seconds < 0.3 or (facts["known_peak"] and facts["peak"] < SILENCE_LEVEL):
            raise VoiceError(MSG_NOTHING_HEARD)  # silence: no call is made, so no cost
    cost = round((seconds if seconds is not None else AUDIO_MAX_SECONDS) / 60 * STT_PRICE_PER_MINUTE, 4)
    return {"format": kind, "seconds": seconds, "cost_usd": cost}


DIGITS = {"zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"}
_DIGIT = r"(?:zero|oh|one|two|three|four|five|six|seven|eight|nine|\d+)"
_DASH = r"(?:[\s,]*(?:-|–|—|dash|hyphen)[\s,]*)"
_DIGITS = rf"{_DIGIT}(?:[\s,.-]+{_DIGIT}){{0,4}}(?![A-Za-z0-9])"
# letters said one at a time ("V P N"), then a dash or just a space, then the digits ... or joined letters ("VPN") that MUST be followed by a spoken dash
SPELLED = re.compile(rf"(?<![A-Za-z0-9])(?:(?P<spaced>(?:[A-Za-z][\s.,]+){{1,5}}[A-Za-z])(?P<d1>{_DASH}|\s+)|(?P<joined>[A-Za-z]{{2,6}})(?P<d2>[\s,]*(?:dash|hyphen)[\s,]*))(?P<digits>{_DIGITS})", re.IGNORECASE)


def _fix(match: re.Match) -> str:
    letters = re.sub(r"[^A-Za-z]", "", match.group("spaced") or match.group("joined"))
    digits = "".join(DIGITS.get(part.lower(), part) for part in re.findall(r"[A-Za-z]+|\d+", match.group("digits")))
    if not (2 <= len(letters) <= 6 and 2 <= len(digits) <= 5):
        return match.group(0)
    if match.group("d1") is not None and not match.group("d1").strip() and len(letters) < 3:
        return match.group(0)  # no spoken dash, so "I a 12" is not a code: it needs at least 3 letters
    return f"{letters.upper()}-{digits}"


def normalise_codes(text: str) -> str:
    """Turn error codes that were spelled out loud into the written form: "V P N dash eight zero nine" -> "VPN-809".

    Letters said one by one (or joined, when a spoken "dash" follows) and then digits said as words or numbers. A code needs 2 to 6
    letters and 2 to 5 digits, so ordinary words and numbers are left alone.
    """
    return SPELLED.sub(_fix, text)


@lru_cache(maxsize=1)
def known_prefixes() -> frozenset:
    """The letters that error codes start with in the knowledge base (VPN, WIFI, ...), so only a real code is put in capitals."""
    from app.loader import load_documents
    found = set()
    for doc in load_documents():
        for _, text in doc["pages"]:
            found.update(re.findall(r"(?<![A-Za-z0-9])([A-Z]{2,6})-\d{2,5}(?![A-Za-z0-9])", text))
    return frozenset(found)


def clean_transcript(text: str) -> str:
    """The transcript as a one-line question: no control characters, spaces tidied, spelled codes fixed."""
    text = re.sub(r"[\x00-\x1f\x7f]", " ", text or "")
    text = normalise_codes(" ".join(text.split()))
    prefixes = known_prefixes()
    return re.sub(r"(?<![A-Za-z0-9])([A-Za-z]{2,6})-(\d{2,5})(?![A-Za-z0-9])",
                  lambda m: f"{m.group(1).upper()}-{m.group(2)}" if m.group(1).upper() in prefixes else m.group(0), text)  # vpn-809 -> VPN-809, but pre-2020 stays


def transcribe(data: bytes, stt=call_stt) -> dict:
    """Check the recording, turn it into text and clean the text. Returns {text, seconds, cost_usd, format}.

    Raises VoiceError for a bad, silent or too long recording, and for a transcript with nothing in it. An unreachable speech model
    raises LLMError (the caller shows the usual friendly message).
    """
    facts = check_recording(data)
    text = clean_transcript(stt(data, facts["format"], facts["seconds"] or 0.0))
    if not re.search(r"[A-Za-z0-9]{2}", text):
        raise VoiceError(MSG_NOTHING_HEARD)
    log_call({"kind": "voice", "stt_calls": 1, "audio_seconds": round(facts["seconds"] or 0, 1), "cost_usd": facts["cost_usd"]})  # numbers only: no audio, no text
    return {"text": text, **facts}
