"""ffmpeg helpers (Day 2, prompts 8 and 12): turn a browser recording into a wav, make silence, join clips, read a duration.

ffmpeg comes from the system if it is installed, otherwise from the pip package imageio-ffmpeg (no installer needed).
"""
import re
import shutil
import subprocess
import wave
from functools import lru_cache
from pathlib import Path


class AudioError(Exception):
    """ffmpeg is missing or could not read a file. The message is safe to show on a page."""


@lru_cache
def ffmpeg_exe() -> str:
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:
        raise AudioError("ffmpeg is not installed: run  pip install imageio-ffmpeg  or install ffmpeg") from e


def _run(args: list[str]) -> str:
    try:
        done = subprocess.run([ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "error", *args], capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise AudioError(f"ffmpeg could not run: {e}") from e
    if done.returncode != 0:
        raise AudioError("The recording could not be read: " + (done.stderr.strip().splitlines() or ["unknown error"])[-1][:200])
    return done.stderr


def to_wav(src: Path, dst: Path, rate: int = 16000) -> Path:
    """Any audio file (a browser's webm, an m4a, an mp3) to a mono wav at one sample rate. Raises AudioError with a clear message if it fails."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    _run(["-i", str(src), "-ac", "1", "-ar", str(rate), "-sample_fmt", "s16", str(dst)])
    return dst


def silent_wav(path: Path, seconds: float, rate: int = 16000) -> Path:
    """A silent mono wav (written directly, no ffmpeg needed)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(rate * max(0.05, seconds)))
    return path


def duration(path: Path) -> float:
    """Seconds of audio in a file of any format ffmpeg reads (wav is read directly)."""
    try:
        with wave.open(str(path), "rb") as w:
            return round(w.getnframes() / w.getframerate(), 3)
    except Exception:
        pass
    try:
        done = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", str(path)], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired, AudioError):
        return 0.0
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", done.stderr)
    return round(int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)), 3) if m else 0.0


def join(wavs: list[Path], out_mp3: Path, rate: int = 16000) -> Path:
    """Joins wav clips, in the order given, into one mp3 (or one wav, if the output name ends in .wav). Every clip must already be a wav at the same sample rate."""
    if not wavs:
        raise AudioError("There is no audio to join")
    out_mp3.parent.mkdir(parents=True, exist_ok=True)
    listing = out_mp3.parent / "_clips.txt"
    listing.write_text("".join(f"file '{Path(w).resolve().as_posix()}'\n" for w in wavs), encoding="utf-8")
    try:
        codec = ["-codec:a", "pcm_s16le"] if out_mp3.suffix.lower() == ".wav" else ["-codec:a", "libmp3lame", "-q:a", "5"]
        _run(["-f", "concat", "-safe", "0", "-i", str(listing), "-ac", "1", "-ar", str(rate), *codec, str(out_mp3)])
    finally:
        listing.unlink(missing_ok=True)
    return out_mp3
