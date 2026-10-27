"""Speech to text and text to speech. The only place a speech model is called.

FAKE_MODELS=1: transcription reads the .transcript.txt that sits next to every recorded fixture (so tests never run a model),
and speech is not synthesised (the interview page speaks with the browser). FAKE_MODELS=0: faster-whisper transcribes, and
pyttsx3 (the operating system's voices) or your provider's text-to-speech speaks.
"""
import wave
from pathlib import Path

from app.config import get_settings

FIXTURE_DIRS = ["recorded_answers", "accent_set", "human_interviews", "voice_notes"]


def _sidecar(path: Path, original_name: str) -> Path | None:
    s = get_settings()
    stem = Path(original_name or path.name).stem
    candidates = [path.with_suffix(".transcript.txt"), Path(s.fake_transcripts_dir) / f"{stem}.transcript.txt"]
    candidates += [Path(s.kit_dir) / d / f"{stem}.transcript.txt" for d in FIXTURE_DIRS]
    return next((c for c in candidates if c.exists()), None)


def transcribe(path: Path, original_name: str = "") -> str:
    s = get_settings()
    if s.fake_models:
        side = _sidecar(path, original_name)
        if side is None:
            raise FileNotFoundError(f"No fake transcript for {Path(original_name or path.name).name}: in fake mode only the recorded fixtures can be transcribed")
        return side.read_text(encoding="utf-8").strip()
    from faster_whisper import WhisperModel  # imported late: it is slow to import and not needed in tests

    model = WhisperModel(s.whisper_model, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(str(path), language="en", vad_filter=True)
    return " ".join(seg.text.strip() for seg in segments).strip()


def transcribe_segments(path: Path) -> list[dict]:
    """[{start, end, text}] for a recording. Fake mode has no timing, so it returns the whole text as one segment."""
    s = get_settings()
    if s.fake_models:
        return [{"start": 0.0, "end": audio_duration(path), "text": transcribe(path)}]
    from faster_whisper import WhisperModel

    model = WhisperModel(s.whisper_model, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(str(path), language="en", vad_filter=True)
    return [{"start": round(g.start, 2), "end": round(g.end, 2), "text": g.text.strip()} for g in segments]


def audio_duration(path: Path) -> float:
    """Seconds of audio (WAV). Other formats are estimated from the file size."""
    try:
        with wave.open(str(path), "rb") as w:
            return round(w.getnframes() / w.getframerate(), 2)
    except Exception:
        try:
            return round(path.stat().st_size / 16000.0, 2)
        except OSError:
            return 0.0


def speaking_seconds(text: str) -> float:
    """How long a text takes to say aloud (about 2.5 words a second): used for the 25-minute interview limit."""
    return round(len(text.split()) / 2.5, 2)


def speak(text: str, out: Path | None = None) -> dict:
    """Text to speech. Returns {"text", "duration_s", "file"}. In fake mode nothing is synthesised: the page speaks it in the browser."""
    info = {"text": text, "duration_s": speaking_seconds(text), "file": None}
    if get_settings().fake_models or out is None:
        return info
    try:
        import pyttsx3

        engine = pyttsx3.init()
        out.parent.mkdir(parents=True, exist_ok=True)
        engine.save_to_file(text, str(out))
        engine.runAndWait()
        info["file"] = str(out)
    except Exception:
        pass  # the browser can still speak it
    return info
