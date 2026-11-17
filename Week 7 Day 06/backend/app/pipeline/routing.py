"""Ticket ENG-602: decide, for each field, whether it goes straight through or to the Review queue.

Two signals, because one is not enough:
- confidence: how sure the OCR is of the words the value was read from (Day 3). It catches smudges and misreads.
- agreement: whether the vision model read the same value. It catches the model choosing the wrong words with
  perfect confidence, such as a statement period's end date instead of the statement date (Day 4's top failure).
"""

import re

from app.pipeline.models import Route
from app.prototype.models import Field

OK_AT = 0.85  # the Day 3 threshold: a field below it goes to a person


def norm(text: str) -> str:
    """Lower case, letters and digits only: the comparison the evaluation uses."""
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def route_field(parser: Field, vision: Field | None = None, ok_at: float = OK_AT, use_agreement: bool = True) -> Route:
    """Route one field read by the parser method, checked against the same field read by the vision model.

    Collect the reasons to send it to a person, in this order:
    1. parser.status is "missing" or "not_on_page": the reason is parser.note (or "Not found on the page" if the note is empty).
       Otherwise, when parser.confidence < ok_at: f"OCR confidence {parser.confidence:.2f} is below {ok_at:.2f}".
    2. use_agreement is True, vision is not None, and norm(vision.value) != norm(parser.value):
       f'The vision model read "{vision.value}"' (or "The vision model found no value" when vision.value is empty).
    No reasons: Route(decision="auto", reasons=[]). Any reason: Route(decision="review", reasons=<the reasons>).
    A field a person has already confirmed (status "confirmed") is always "auto", with no reasons.
    """
    if parser.status == "confirmed":
        return Route(decision="auto", reasons=[])
    reasons = []
    if parser.status in ("missing", "not_on_page"):
        reasons.append(parser.note or "Not found on the page")
    elif parser.confidence < ok_at:
        reasons.append(f"OCR confidence {parser.confidence:.2f} is below {ok_at:.2f}")
    if use_agreement and vision is not None and norm(vision.value) != norm(parser.value):
        reasons.append(f'The vision model read "{vision.value}"' if vision.value else "The vision model found no value")
    return Route(decision="review", reasons=reasons) if reasons else Route(decision="auto", reasons=[])
