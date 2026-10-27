"""Replays a recorded two-channel interview as if it were live (Day 3): one event per finished utterance, in time order.

speed = replay seconds per real second. speed=0 replays instantly (tests); speed=1 is real time; speed=8 is eight times faster.
"""
import json
import time
from pathlib import Path
from typing import Iterator

from app.config import get_settings


def load_interviews() -> list[dict]:
    path = Path(get_settings().kit_dir) / "human_interviews" / "interviews.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def get_interview(interview_id: str) -> dict | None:
    return next((i for i in load_interviews() if i["id"] == interview_id), None)


def replay(interview: dict, speed: float = 0.0) -> Iterator[dict]:
    """Yields {"speaker", "text", "start", "end"} for each turn, sleeping so that events arrive at (replay time / speed)."""
    started = time.perf_counter()
    for t in interview["turns"]:
        if speed > 0:
            wait = t["end"] / speed - (time.perf_counter() - started)
            if wait > 0:
                time.sleep(wait)
        yield {"speaker": t["speaker"], "text": t["text"], "start": t["start"], "end": t["end"]}
