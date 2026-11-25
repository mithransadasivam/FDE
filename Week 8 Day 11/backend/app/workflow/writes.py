"""Ticket ENG-1003: every write happens once, even when the worker crashes halfway through a step.

DBOS saves a step's output when the step finishes. If the worker dies after the step has written to the bank but before the
step finished, the step runs again when the worker comes back: "at least once". To make the write itself happen once, each
write must be safe to make twice:

  - The contact gateway takes an Idempotency-Key header: the same key twice sends one message. The key must be the same
    every time the same step runs again, and different for every other write.
  - CaseFlow Classic has no API and no keys. So the step writes a marker into the note, and before it writes, it reads the
    case history: if its marker is already there, the outcome was recorded by the attempt that crashed.

data/Day10_Slide21_writes.csv lists every write the case workflow makes, and how each one is made safe.
"""

import httpx

from app.config import BANK_URL


def idempotency_key(workflow_id: str, step_id: int) -> str:
    """The Idempotency-Key for the write made by step `step_id` of workflow `workflow_id`.

    The same workflow and step give the same key, every time the step runs: f"{workflow_id}:{step_id}".
    Never a random value or the time: a new key for each attempt is no key at all.
    """
    return f"{workflow_id}:{step_id}"


def outcome_marker(workflow_id: str, round_no: int) -> str:
    """The marker the apply step puts at the end of its CaseFlow note: f"[{workflow_id} r{round_no}]"."""
    return f"[{workflow_id} r{round_no}]"


def already_recorded(history: list[str], marker: str) -> bool:
    """True if a line of the case history contains `marker` exactly, brackets included.

    "[case-KX-1001-1 r1]" is in "Outcome: Request more information (R02). … [case-KX-1001-1 r1] Reference OUT-40017.",
    but "[case-KX-1001-1 r1]" is not in a line that has "[case-KX-1001-1 r12]" or "[case-KX-1001-11 r1]".
    """
    return any(marker in line for line in history)


# ---------------------------------------------------------------- the writes themselves (done)
def post(token: str, path: str, body: dict, key: str | None) -> dict:
    """POST to one of the bank's systems, with an Idempotency-Key header when `key` is given."""
    headers = {"Authorization": f"Bearer {token}", **({"Idempotency-Key": key} if key else {})}
    r = httpx.post(f"{BANK_URL}{path}", json=body, headers=headers, timeout=20)
    if r.status_code >= 400:
        try:
            why = r.json().get("detail", r.text)
        except ValueError:
            why = r.text
        raise RuntimeError(f"{path} refused: {why}")
    return r.json()
