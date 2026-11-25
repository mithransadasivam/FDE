"""Ticket ENG-1103: the cascade. The small model reads every document; the pilot (Sonnet 5, ADR-003) reads the
documents the small model is not sure of.

A document goes through on the small model alone only when all four of its fields are sure enough. One unsure field
is enough to send the whole document to the pilot: the pilot reads a page, not a field, so it costs the same.

Example, at a threshold of 0.80: full_name 0.97, address 0.95, statement_date 0.59, issuer 0.96. The average is 0.87,
but the statement date is a guess. The document goes to the pilot, with the reason "statement_date 0.59 below 0.80".
A field with no value ("" and confidence 0) goes to the pilot with the reason "statement_date missing".

Spot checks (done): one confident document in twenty goes to the pilot as well, chosen from its id, so the team can
see how often the small model and the teacher still agree. The same document is always checked, on every run.
"""

import hashlib
import math

from pydantic import BaseModel

from app.distil.reader import SmallField


class Decision(BaseModel):
    route: str  # "small": the small model's values go through · "teacher": the pilot reads the document
    reasons: list[str] = []


def route_document(fields: list[SmallField], threshold: float) -> Decision:
    """"small" when every field has a value and a confidence of at least `threshold`; otherwise "teacher".
    reasons: one per field that sends the document to the teacher, in the order of `fields`:
    "<name> missing" when the value is "", or "<name> <confidence> below <threshold>", both with 2 decimals; the
    confidence rounded down (math.floor(confidence * 100 + 1e-9) / 100), so 0.699 is "0.69 below 0.70".
    """
    reasons = []
    for f in fields:
        if not f.value:
            reasons.append(f"{f.name} missing")
        elif f.confidence < threshold:
            reasons.append(f"{f.name} {math.floor(f.confidence * 100 + 1e-9) / 100:.2f} below {threshold:.2f}")
    return Decision(route="teacher", reasons=reasons) if reasons else Decision(route="small")


def spot_check(doc_id: str, per_hundred: int = 5) -> bool:
    """Is this confident document one of the ones the teacher reads anyway? The same answer every time for an id."""
    return int(hashlib.sha256(doc_id.encode()).hexdigest()[:8], 16) % 100 < per_hundred
