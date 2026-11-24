"""The contract for the UC1 prototype: every session (backend, rules, UI) builds against these shapes.
The same shapes are in frontend/src/api.ts. Change them only by agreement, in the main checkout."""

from typing import Literal

from pydantic import BaseModel, Field as PField

FieldName = Literal["full_name", "address", "statement_date", "issuer"]
FIELDS: list[str] = ["full_name", "address", "statement_date", "issuer"]
FIELD_LABELS = {"full_name": "Full name", "address": "Address", "statement_date": "Statement date", "issuer": "Issuer"}

# ok: trust it · check: a person should glance at it · doubtful: a person must read it
# not_on_page: the model's value is not what the cited words say · missing: no value at all
# confirmed: a person accepted or corrected it in the review screen
Status = Literal["ok", "check", "doubtful", "not_on_page", "missing", "confirmed"]


class OcrWord(BaseModel):
    """One word from the OCR service: its text, where it is on the page (0–1 of the page width and
    height: x0, y0, x1, y1) and how sure the OCR is (0–1). Shaped like Amazon Textract's WORD blocks."""
    id: str
    text: str
    box: list[float]
    confidence: float


class ModelField(BaseModel):
    """What the model returns for one field: the value, and the ids of the OCR words it read it from."""
    name: str
    value: str = ""
    word_ids: list[str] = PField(default_factory=list)


class ExtractionReply(BaseModel):
    fields: list[ModelField]


class Field(BaseModel):
    """A field ready for the review screen."""
    name: str
    label: str
    value: str
    confidence: float  # 0–1; 0 when the value cannot be grounded on the page
    status: Status
    box: list[float] | None = None  # the union of the cited words' boxes, or None
    page_text: str = ""  # what the cited words actually say
    note: str = ""


class Application(BaseModel):
    case_id: str
    applicant_name: str
    address_line1: str
    town: str
    postcode: str
    application_date: str  # ISO date
    received_date: str  # ISO date: when the document arrived for review
    channel: str
    document: str


class Check(BaseModel):
    id: Literal["name", "address", "date", "issuer"]
    label: str
    status: Literal["pass", "fail", "look"]  # look: a person must confirm a field first
    detail: str
