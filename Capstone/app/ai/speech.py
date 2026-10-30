"""Text to speech that saves a file (Day 2, prompt 8). The SERVER speaks each question into a wav, so the interview can be replayed
and joined into one recording later (a browser's own voice leaves nothing to save).

speak(text, path)  writes a wav with an offline engine: pyttsx3 (the operating system's voices), or espeak-ng if installed.
                   In fake mode it writes a short silent wav instead (tests never wait for a voice). If no engine works it logs a
                   warning and returns None: the page then shows the question text only.
"""
import hashlib
import logging
import shutil
import subprocess
import time
from pathlib import Path

from app.ai import ledger
from app.ai.audio import silent_wav
from app.config import get_settings

log = logging.getLogger("speech")

# Two clearly different voices: the interviewer, and (for sample interviews with a simulated candidate) the candidate.
VOICES = {"interviewer": {"index": 0, "rate": 175}, "candidate": {"index": 1, "rate": 150}}


def _fake_seconds(text: str) -> float:
    return min(1.5, 0.3 + 0.02 * len((text or "").split()))  # short: just enough to have a file with a length


def _pyttsx3(text: str, path: Path, voice: str) -> bool:
    try:
        import pyttsx3

        engine = pyttsx3.init()
        v = VOICES.get(voice, VOICES["interviewer"])
        voices = engine.getProperty("voices")
        if voices:
            engine.setProperty("voice", voices[min(v["index"], len(voices) - 1)].id)
        engine.setProperty("rate", v["rate"])
        engine.save_to_file(text, str(path))
        engine.runAndWait()
        engine.stop()
        return path.exists() and path.stat().st_size > 1000
    except Exception as e:
        log.warning("pyttsx3 could not speak: %s", e)
        return False


def _espeak(text: str, path: Path, voice: str) -> bool:
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe:
        return False
    try:
        subprocess.run([exe, "-w", str(path), "-s", "150" if voice == "candidate" else "175", "-v", "en-us+f3" if voice == "candidate" else "en-us", text],
                       check=True, capture_output=True, timeout=60)
        return path.exists()
    except Exception as e:
        log.warning("espeak-ng could not speak: %s", e)
        return False


def speak(text: str, path: Path, voice: str = "interviewer", real: bool | None = None) -> Path | None:
    """Writes `text` spoken aloud to `path` (a wav) and returns the path, or None if no voice is available.
    real=True forces a real voice even in fake mode (the sample interviews are made to be listened to); the default follows FAKE_MODELS."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    use_real = (not get_settings().fake_models) if real is None else real
    if not use_real:
        return silent_wav(path, _fake_seconds(text))
    from app import timing

    cached = _cache_file(text, voice)
    started = time.perf_counter()
    with timing.timed("speech"):
        if cached is not None and cached.exists():  # a fixed question has been spoken before: reuse the recording (no personal data is in it)
            shutil.copyfile(cached, path)
            ledger.record_timed("speech", "text_to_speech (cached)", time.perf_counter() - started)
            return path
        if _pyttsx3(text, path, voice) or _espeak(text, path, voice):
            if cached is not None:
                cached.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, cached)
            ledger.record_timed("speech", "text_to_speech", time.perf_counter() - started)
            return path
    log.warning("No text-to-speech voice is available: the question will be shown as text only")
    return None


def _fixed_texts() -> set[str]:
    """The questions that are the same for every candidate (the question guide's own wording). Written questions mention the CV, so they are never cached."""
    from app.interview.bank import load_questions

    out: set[str] = set()
    for q in load_questions().values():
        out.add(q["question"])
        out.update(q.get("follow_ups") or [])
    return out


def _cache_file(text: str, voice: str) -> Path | None:
    if not getattr(get_settings(), "speech_cache", True) or text not in _fixed_texts():
        return None
    return get_settings().storage_dir / "tts_cache" / (hashlib.sha256(f"{voice}|{text}".encode()).hexdigest()[:24] + ".wav")
