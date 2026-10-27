"""Speech to text. The only place a speech model is called (Prompt 6)."""
from pathlib import Path

from app.config import get_settings


def transcribe(path: Path, original_name: str = "") -> str:
    s = get_settings()
    if s.fake_models:
        # Fake mode: the starter kit ships the words of each voice note next to it.
        side = Path(s.fake_transcripts_dir) / (Path(original_name or path.name).stem + ".transcript.txt")
        if not side.exists():
            raise FileNotFoundError(f"No fake transcript for {Path(original_name or path.name).name} (looked for {side.name})")
        return side.read_text(encoding="utf-8").strip()
    from faster_whisper import WhisperModel  # imported late: it is slow to import and not needed in tests

    model = WhisperModel(s.whisper_model, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(str(path), language="en", vad_filter=True)
    return " ".join(seg.text.strip() for seg in segments).strip()
