"""Saves the team's work as readable files in engagement/, so it can be committed and reviewed."""

import json
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
    path(name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_text(name: str) -> str:
    p = path(name)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def save_text(name: str, text: str) -> None:
    path(name).write_text(text, encoding="utf-8")
