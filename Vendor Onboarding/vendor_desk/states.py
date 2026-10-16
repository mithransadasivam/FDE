"""Explicit case states and the only moves between them (Phase 9).

The diagram (drawn before the code, see docs/DECISIONS.md):

    RECEIVED ──► CHECKING ──► READY_FOR_APPROVAL ──► APPROVED ──► CREATED
                  │  ▲  ▲          │   │  ▲              │
                  │  │  │          │   │  └── (release)  │
                  ▼  │  │          │   ▼                 ▼
          WAITING_FOR_VENDOR ◄──────┘  REJECTED        STOPPED
                  │                                       ▲
                  └──► REJECTED     STOPPED ──► CHECKING / READY_FOR_APPROVAL / REJECTED

Rules enforced in code, not by convention:
  * any move not in ALLOWED raises IllegalMove (and nothing changes)
  * moves that are a person's decision (approve, reject, release a stopped case, ask the vendor) are refused unless
    `by_person=True`: a system step can never approve or reject
  * CREATED is reachable only from APPROVED, and APPROVED only from READY_FOR_APPROVAL
  * every move is recorded with the time, who made it and the reason
"""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum


class State(str, Enum):
    RECEIVED = "RECEIVED"
    CHECKING = "CHECKING"
    WAITING_FOR_VENDOR = "WAITING_FOR_VENDOR"
    READY_FOR_APPROVAL = "READY_FOR_APPROVAL"
    APPROVED = "APPROVED"
    CREATED = "CREATED"
    REJECTED = "REJECTED"
    STOPPED = "STOPPED"


S = State
ALLOWED: dict[State, set[State]] = {
    S.RECEIVED: {S.CHECKING, S.STOPPED},
    S.CHECKING: {S.WAITING_FOR_VENDOR, S.READY_FOR_APPROVAL, S.STOPPED},
    S.WAITING_FOR_VENDOR: {S.CHECKING, S.REJECTED, S.STOPPED},
    S.READY_FOR_APPROVAL: {S.APPROVED, S.WAITING_FOR_VENDOR, S.REJECTED, S.STOPPED},
    S.APPROVED: {S.CREATED, S.STOPPED},
    S.STOPPED: {S.CHECKING, S.READY_FOR_APPROVAL, S.REJECTED},
    S.CREATED: set(),
    S.REJECTED: set(),
}
TERMINAL = {S.CREATED, S.REJECTED}

# moves that only a person may make
PERSON_ONLY = {
    (S.READY_FOR_APPROVAL, S.APPROVED), (S.READY_FOR_APPROVAL, S.REJECTED), (S.READY_FOR_APPROVAL, S.WAITING_FOR_VENDOR),
    (S.WAITING_FOR_VENDOR, S.REJECTED), (S.STOPPED, S.READY_FOR_APPROVAL), (S.STOPPED, S.REJECTED),
    (S.STOPPED, S.CHECKING),
}


class IllegalMove(Exception):
    """A move the state machine refuses."""


@dataclass
class Move:
    at: str
    from_state: str | None
    to_state: str
    reason: str
    actor: str
    by_person: bool

    def as_dict(self) -> dict:
        return asdict(self)


def check_move(current: State | None, target: State, by_person: bool = False) -> None:
    if current is None:
        if target != S.RECEIVED:
            raise IllegalMove(f"A new case must start as RECEIVED, not {target.value}.")
        return
    if target not in ALLOWED[current]:
        raise IllegalMove(f"{current.value} -> {target.value} is not an allowed move.")
    if (current, target) in PERSON_ONLY and not by_person:
        raise IllegalMove(f"{current.value} -> {target.value} is a person's decision; the system cannot make it.")


def make_move(current: State | None, target: State, reason: str, actor: str = "system",
              by_person: bool = False) -> Move:
    """Validate the move and return its record (time, who, why). Raises IllegalMove without changing anything."""
    target = State(target)
    current = State(current) if current is not None else None
    if not reason.strip():
        raise IllegalMove("Every move needs a reason.")
    check_move(current, target, by_person)
    return Move(datetime.now(timezone.utc).isoformat(timespec="seconds"), current.value if current else None,
                target.value, reason, actor, by_person)


class RetryBudget:
    """Bounded retries (Phase 9): when a limit is reached the caller moves the case to STOPPED with the reason."""

    def __init__(self, handoff_limit: int, tool_error_limit: int):
        self.limits = {"handoff": handoff_limit, "tool_error": tool_error_limit}
        self.used = {"handoff": 0, "tool_error": 0}

    def record(self, kind: str, n: int = 1) -> str | None:
        """Count n failures; return the stop reason if the limit has been reached, else None."""
        self.used[kind] += n
        if self.used[kind] >= self.limits[kind]:
            what = "handoff failures" if kind == "handoff" else "tool errors"
            return f"Stopped after {self.used[kind]} {what} (limit {self.limits[kind]})."
        return None
