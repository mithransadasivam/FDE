"""Shapes for the Day 6 pipeline. The same shapes are in the Day 6 section of frontend/src/api.ts."""

from typing import Literal

from pydantic import BaseModel

from app.prototype.models import OcrWord

Source = Literal["text_layer", "ocr"]  # text_layer: words read from a digital PDF · ocr: words from the bank's OCR file


class ParsedPage(BaseModel):
    """One document, parsed: its words in reading order, and where they came from."""
    doc_id: str
    file: str  # the file the bank sent: B-001.pdf or B-001.jpg
    source: Source
    words: list[OcrWord]


class Route(BaseModel):
    """Where one field goes: straight through ("auto"), or to the Review queue, with the reasons why."""
    decision: Literal["auto", "review"]
    reasons: list[str] = []
