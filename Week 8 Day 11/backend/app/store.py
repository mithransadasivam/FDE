"""Saves the team's work as readable files in engagement/, so it can be committed and reviewed."""

import json
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path

from app.config import ENGAGEMENT_DIR


def path(name: str) -> Path:
    """engagement/<name>; folders in the name (such as eval/runs/x.json) are created as needed."""
    p = ENGAGEMENT_DIR / name
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load(name: str, default):
    p = path(name)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def save(name: str, data) -> None:
    """Write the whole file at once (a temporary file, then a rename), so another process never reads half of it (Day 10)."""
    p = path(name)
    tmp = p.with_name(f"{p.name}.{os.getpid()}.{threading.get_ident()}.tmp")  # one per process and thread (Day 11: two requests at once)
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for i in range(20):
        try:
            os.replace(tmp, p)
            return
        except PermissionError:  # Windows: a reader has the file open for a moment
            time.sleep(0.05)
    os.replace(tmp, p)


@contextmanager
def locked(name: str, stale_s: float = 10):
    """One process at a time for a read-modify-write of engagement/<name> (the console's API and the workflow worker)."""
    lock = path(name + ".lock")
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            break
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime > stale_s:
                    lock.unlink(missing_ok=True)
            except FileNotFoundError:
                pass
            time.sleep(0.02)
    try:
        yield
    finally:
        lock.unlink(missing_ok=True)


def load_text(name: str) -> str:
    p = path(name)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def save_text(name: str, text: str) -> None:
    path(name).write_text(text, encoding="utf-8")
