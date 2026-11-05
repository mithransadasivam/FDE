"""Ticket ENG-301: ground every field the model returns on the OCR words of the page.

This is what makes the prototype trustworthy (the lesson of the 2024 pilot, and ADR-001):
a field is only as sure as the words it was read from, and a value the page does not show is never trusted.
"""

import re

from app.prototype.models import FIELD_LABELS, FIELDS, ExtractionReply, Field, OcrWord

OK_AT = 0.85  # confidence at or above this: "ok"
CHECK_AT = 0.60  # at or above this, but below OK_AT: "check"; below this: "doubtful"


def norm(text: str) -> str:
    """Lower case, letters and digits only: 'Flat 3, 14 Larkspur Row' -> 'flat314larkspurrow'."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def status_for(confidence: float, ok_at: float = OK_AT, check_at: float = CHECK_AT) -> str:
    if confidence >= ok_at:
        return "ok"
    if confidence >= check_at:
        return "check"
    return "doubtful"


def union_box(boxes: list[list[float]]) -> list[float]:
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]


def ground_fields(reply: ExtractionReply, words: list[OcrWord], ok_at: float = OK_AT, check_at: float = CHECK_AT) -> list[Field]:
    """Return one Field for each name in FIELDS, in that order.

    For each field, find the model's entry in reply.fields by name, then:
    - no entry, or an empty value: value "", confidence 0.0, status "missing", note "Not found on the page"
    - look up the cited words by id (ignore ids that are not on the page). If none are left:
      keep the model's value, confidence 0.0, status "not_on_page", note "The model gave no words from the page"
    - page_text = the cited words' text joined with single spaces, in the order the model cited them
    - if norm(value) != norm(page_text): keep the model's value, confidence 0.0, status "not_on_page",
      note f'The page says "{page_text}"', and still set box and page_text so the screen can show where
    - otherwise: confidence = the lowest confidence of the cited words, rounded to 2 decimals;
      status = status_for(confidence, ok_at, check_at); note ""
    - box = union_box of the cited words' boxes, or None when there are no cited words
    - label = FIELD_LABELS[name]
    """
    by_name = {f.name: f for f in reply.fields}
    by_id = {w.id: w for w in words}
    out = []
    for name in FIELDS:
        label = FIELD_LABELS[name]
        mf = by_name.get(name)
        if mf is None or not mf.value.strip():
            out.append(Field(name=name, label=label, value="", confidence=0.0, status="missing", note="Not found on the page"))
            continue
        cited = [by_id[i] for i in mf.word_ids if i in by_id]
        if not cited:
            out.append(Field(name=name, label=label, value=mf.value, confidence=0.0, status="not_on_page",
                             note="The model gave no words from the page"))
            continue
        page_text = " ".join(w.text for w in cited)
        box = union_box([w.box for w in cited])
        if norm(mf.value) != norm(page_text):
            out.append(Field(name=name, label=label, value=mf.value, confidence=0.0, status="not_on_page",
                             box=box, page_text=page_text, note=f'The page says "{page_text}"'))
            continue
        conf = round(min(w.confidence for w in cited), 2)
        out.append(Field(name=name, label=label, value=mf.value, confidence=conf,
                         status=status_for(conf, ok_at, check_at), box=box, page_text=page_text))
    return out

