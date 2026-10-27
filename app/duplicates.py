"""Duplicate detection (Day 1 stretch): the same person applying in two formats, found by e-mail or phone.

It only flags. A person decides what to do about a duplicate (rule 1), for example by withdrawing one application.
"""
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Candidate


def _email(profile: dict | None) -> str | None:
    v = ((profile or {}).get("email") or {}).get("value")
    return v.strip().lower() if v else None


def _phone(profile: dict | None) -> str | None:
    v = ((profile or {}).get("phone") or {}).get("value")
    digits = re.sub(r"\D", "", v or "")
    return digits[-10:] if len(digits) >= 7 else None  # compares the last 10 digits, so +44 and 0 prefixes still match


def duplicate_map(db: Session, requisition_id: int | None = None) -> dict[int, list[int]]:
    """candidate id -> ids of the other candidates (same job) with the same e-mail or phone number."""
    query = select(Candidate)
    if requisition_id is not None:
        query = query.where(Candidate.requisition_id == requisition_id)
    by_key: dict[tuple[int, str, str], list[int]] = {}
    people = []
    for c in db.scalars(query):
        people.append(c)
        for kind, key in (("email", _email(c.profile)), ("phone", _phone(c.profile))):
            if key:
                by_key.setdefault((c.requisition_id, kind, key), []).append(c.id)
    out: dict[int, list[int]] = {}
    for c in people:
        same: set[int] = set()
        for kind, key in (("email", _email(c.profile)), ("phone", _phone(c.profile))):
            if key:
                same.update(by_key[(c.requisition_id, kind, key)])
        same.discard(c.id)
        if same:
            out[c.id] = sorted(same)
    return out
