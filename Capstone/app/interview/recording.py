"""The full interview recording (Day 2, prompt 12): when an interview finishes, its clips are joined into one mp3 with a timeline.

storage/interviews/<id>/full_conversation.mp3  every question and every submitted answer, in order, with half a second of silence between clips
storage/interviews/<id>/recording.json         for every clip: speaker, start and end (seconds in the full file), text, skill, diagram, level and quote

The timeline is built from the saved turns and the real length of each clip, never guessed. Only interviews whose candidate agreed to
recording (consent_recording) are recorded. Rule 10: recordings are personal data: only staff can open them, every opening is logged, and
scripts/purge_recordings.py deletes old audio.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.ai import audio, voice
from app.config import get_settings
from app.models import DecisionLog
from app.models_ext import InterviewSession

GAP_SECONDS = 0.5
AUDIO_SUFFIXES = {".wav", ".mp3", ".webm", ".ogg", ".m4a"}


def folder_of(s: InterviewSession) -> Path:
    return get_settings().storage_dir / "interviews" / str(s.id)


def mp3_path(s: InterviewSession) -> Path:
    return folder_of(s) / "full_conversation.mp3"


def json_path(s: InterviewSession) -> Path:
    return folder_of(s) / "recording.json"


def _find(ref: str | None) -> Path | None:
    """A saved clip: under the storage folder (the candidate's own recording and the spoken questions) or, for a demo replay, the starter kit."""
    if not ref:
        return None
    for root in (get_settings().storage_dir, Path(get_settings().kit_dir)):
        p = root / ref
        if p.exists():
            return p
    p = Path(ref)
    return p if p.is_absolute() and p.exists() else None


def sequence(s: InterviewSession) -> list[dict]:
    """The clips in the order they were heard: each question (then its hints), then the candidate's answer to it."""
    clips: list[dict] = []
    for t in s.state["turns"]:
        answers = list(t.get("answers", []))
        meta = t.get("meta", [])
        i = 0
        while i < len(meta):
            m = meta[i]
            if m["kind"] == "hint":  # a hint without a question before it cannot happen; skip defensively
                i += 1
                continue
            clips.append({"speaker": "interviewer", "text": m["text"], "audio": m.get("audio"), "skill": t.get("skill"), "kind": m["kind"], "why": m.get("why", ""),
                          "diagram": (m.get("diagram") or {}).get("text"), "diagram_title": (m.get("diagram") or {}).get("title"), "level": None, "quote": ""})
            i += 1
            while i < len(meta) and meta[i]["kind"] == "hint":
                clips.append({"speaker": "interviewer", "text": meta[i]["text"], "audio": meta[i].get("audio"), "skill": t.get("skill"), "kind": "hint",
                              "diagram": None, "level": None, "quote": ""})
                i += 1
            a = answers.pop(0) if answers else None
            if a:
                score = t.get("score") or {}
                clips.append({"speaker": "candidate", "text": a["text"], "audio": a.get("audio"), "skill": t.get("skill"), "kind": "answer", "diagram": None,
                              "level": None if t.get("opening") or t.get("skipped") else score.get("score"),
                              "quote": "" if t.get("opening") else score.get("quote", "")})
    return clips


def build_recording(db: Session, s: InterviewSession) -> dict | None:
    """Builds full_conversation.mp3 and recording.json. Returns the timeline, or None if the interview is not finished or was not consented to."""
    if s.status != "DONE" or not s.consent_recording or not s.state:
        return None
    work = folder_of(s) / "_work"
    work.mkdir(parents=True, exist_ok=True)
    gap = audio.silent_wav(work / "gap.wav", GAP_SECONDS)
    wavs: list[Path] = []
    timeline: list[dict] = []
    clock = 0.0
    try:
        for n, clip in enumerate(sequence(s), 1):
            src = _find(clip["audio"])
            target = work / f"clip_{n:03d}.wav"
            try:
                if src is None:
                    raise audio.AudioError("no audio for this clip")
                audio.to_wav(src, target)  # every clip is brought to the same format and sample rate before joining
            except audio.AudioError:
                audio.silent_wav(target, max(0.5, voice.speaking_seconds(clip["text"])))  # a typed answer has no sound: keep its place in the timeline
            length = audio.duration(target)
            if wavs:
                wavs.append(gap)
                clock += GAP_SECONDS
            wavs.append(target)
            timeline.append({"n": n, "speaker": clip["speaker"], "kind": clip["kind"], "start": round(clock, 2), "end": round(clock + length, 2),
                             "text": clip["text"], "skill": clip["skill"], "why": clip.get("why", ""), "diagram": clip["diagram"], "diagram_title": clip.get("diagram_title"),
                             "level": clip["level"], "quote": clip["quote"]})
            clock += length
        audio.join(wavs, mp3_path(s))
    finally:
        for f in work.glob("*"):
            f.unlink(missing_ok=True)
        work.rmdir()
    doc = {"interview_id": s.id, "candidate_id": s.candidate_id, "sample": bool(s.sample), "built_at": datetime.now(timezone.utc).isoformat(),
           "duration": round(clock, 2), "audio_file": "full_conversation.mp3", "clips": timeline}
    json_path(s).write_text(json.dumps(doc, indent=1), encoding="utf-8")
    s.recording_built_at = datetime.now(timezone.utc)
    db.add(DecisionLog(actor="system", action="recording built", subject=f"interview:{s.id}", reason=f"{len(timeline)} clips, {doc['duration']} seconds"))
    db.commit()
    return doc


def build_recording_job(interview_id: int) -> None:
    """Runs after the candidate's last answer has been answered (a background task): the page has already replied."""
    from app.db import SessionLocal

    with SessionLocal() as db:
        s = db.get(InterviewSession, interview_id)
        if s is not None:
            build_recording(db, s)


def load_timeline(s: InterviewSession) -> dict | None:
    p = json_path(s)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
