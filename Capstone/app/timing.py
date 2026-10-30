"""Where the time goes when the interviewer answers (Day 4, prompt 5).

begin() starts a stopwatch for one answer; timed("scoring") around a step adds its seconds; finish() saves one ResponseTiming row: the seconds from the
candidate's answer to the next question being playable, split into transcription, scoring, question writing, diagram and speech. If no stopwatch is
running (a test, a script) timed() does nothing, so it never changes behaviour.
"""
import time
from contextlib import contextmanager
from contextvars import ContextVar

from app.config import get_settings
from app.db import OpsSession
from app.models_ext import ResponseTiming

STEPS = ("transcription", "scoring", "question", "diagram", "speech")
_CURRENT: ContextVar[dict | None] = ContextVar("response_steps", default=None)


def begin(transcription_s: float = 0.0) -> None:
    """Starts the stopwatch for one answer. transcription_s is time already spent transcribing it (the record step comes before submit)."""
    _CURRENT.set({"started": time.perf_counter(), **{s: 0.0 for s in STEPS}, "transcription": transcription_s})


@contextmanager
def timed(step: str):
    cur = _CURRENT.get()
    t0 = time.perf_counter()
    try:
        yield
    finally:
        if cur is not None:
            cur[step] = cur.get(step, 0.0) + time.perf_counter() - t0


def finish(candidate_id: int, turn: int | None = None) -> dict | None:
    cur = _CURRENT.get()
    _CURRENT.set(None)
    if cur is None:
        return None
    parts = {s: round(cur[s], 4) for s in STEPS}
    row = {"candidate_id": candidate_id, "turn": turn, **parts, "total_s": round(sum(parts.values()), 4), "simulated": get_settings().fake_models}
    try:
        with OpsSession() as db:
            db.add(ResponseTiming(**row))
            db.commit()
    except Exception:  # timing must never break an interview
        pass
    return row
