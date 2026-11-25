"""Ticket ENG-1102: from the small model's word labels to four fields, each with a confidence you can route on.

The model gives every word five probabilities, one per label (O, full_name, address, statement_date, issuer).
A field's value is the words whose most likely label is that field, in reading order.

A field's confidence must say how likely the value is to be right. Two things can make it wrong:
- the model is unsure which words belong to the field (its probability for a word is low), and
- the words themselves were misread: a smudged "04" that the bank's OCR read as "01", with OCR confidence 0.61.
  The model sees the text "01", not the smudge, so its own probability can be high for a wrong value.

A value is only as good as its weakest word. Example: statement_date from "01" (probability 0.97, OCR 0.61),
"Sep" (0.99, OCR 0.98), "2026" (0.98, OCR 0.97): 0.97 × 0.61 = 0.59, 0.99 × 0.98 = 0.97, 0.98 × 0.97 = 0.95.
The confidence is 0.59, the lowest of the three: this date should not go through on its own.
"""

from pydantic import BaseModel

from app.prototype.models import FIELD_LABELS, FIELDS, OcrWord


class SmallField(BaseModel):
    name: str
    label: str
    value: str
    word_ids: list[str]
    confidence: float  # 0–1: how likely the value is to be right; 0 when no word was found


def read_fields(words: list[OcrWord], probs, classes: list[str]) -> list[SmallField]:
    """The four fields, in the order of FIELDS. probs[i][classes.index(label)] is the model's probability that
    words[i] has that label.
    - The field's words: every word whose most likely label (the highest of its five probabilities) is the field,
      in reading order. value = their texts joined with single spaces; word_ids = their ids.
    - confidence = the lowest, over the field's words, of (the model's probability for the field × the word's OCR
      confidence), rounded to 3 decimals.
    - No word for the field: value "", word_ids [], confidence 0.0.
    """
    out = []
    for f in FIELDS:
        j = classes.index(f)
        mine = [i for i in range(len(words)) if classes[int(probs[i].argmax())] == f]
        conf = round(float(min(probs[i][j] * words[i].confidence for i in mine)), 3) if mine else 0.0
        out.append(SmallField(name=f, label=FIELD_LABELS[f], value=" ".join(words[i].text for i in mine),
                              word_ids=[words[i].id for i in mine], confidence=conf))
    return out
