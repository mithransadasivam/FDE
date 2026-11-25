"""Ticket ENG-1102: four fields from the small model's word labels, each with a confidence you can route on."""

import numpy as np
import pytest

from app.distil import service
from app.distil.reader import read_fields
from app.prototype.models import FIELDS
from tests.distilkit import ocr_words, trained

CLASSES = ["O", "full_name", "address", "statement_date", "issuer"]


def P(*rows):
    return np.array(rows, dtype=float)


def test_a_field_is_its_words_in_reading_order():
    ws = ocr_words(("Statement", 1.0), ("date", 1.0), ("06", 1.0), ("Oct", 1.0), ("2026", 1.0))
    probs = P([.9, 0, 0, .1, 0], [.9, 0, 0, .1, 0], [.1, 0, 0, .9, 0], [.1, 0, 0, .9, 0], [.2, 0, 0, .8, 0])
    f = read_fields(ws, probs, CLASSES)[2]
    assert f.name == "statement_date" and f.value == "06 Oct 2026" and f.word_ids == ["w003", "w004", "w005"]


def test_the_four_fields_come_in_order_with_their_labels():
    ws = ocr_words(("x", 1.0))
    out = read_fields(ws, P([1, 0, 0, 0, 0]), CLASSES)
    assert [f.name for f in out] == FIELDS and [f.label for f in out] == ["Full name", "Address", "Statement date", "Issuer"]


def test_confidence_is_the_weakest_word_times_its_ocr_confidence():
    ws = ocr_words(("01", 0.61), ("Sep", 0.98), ("2026", 0.97))  # the slide's example: a smudged "04" read as "01"
    probs = P([.03, 0, 0, .97, 0], [.01, 0, 0, .99, 0], [.02, 0, 0, .98, 0])
    assert read_fields(ws, probs, CLASSES)[2].confidence == pytest.approx(0.592, abs=1e-3)


def test_a_digital_pdf_word_is_exact_so_only_the_model_counts():
    ws = ocr_words(("Mr", 1.0), ("Ali", 1.0))
    probs = P([.1, .9, 0, 0, 0], [.3, .7, 0, 0, 0])
    assert read_fields(ws, probs, CLASSES)[0].confidence == pytest.approx(0.7)


def test_a_field_with_no_words_is_empty_with_confidence_zero():
    ws = ocr_words(("x", 1.0))
    f = read_fields(ws, P([1, 0, 0, 0, 0]), CLASSES)[3]
    assert (f.value, f.word_ids, f.confidence) == ("", [], 0.0)


def test_the_classes_order_comes_from_the_model():
    ws = ocr_words(("Ali", 1.0))
    classes = ["address", "full_name", "issuer", "O", "statement_date"]  # a different order
    f = read_fields(ws, P([0, .8, 0, .2, 0]), classes)[0]
    assert f.value == "Ali" and f.confidence == pytest.approx(0.8)


def test_on_a_smudged_october_statement_the_date_is_not_trusted():
    """B-012: the bank's OCR read a smudged "04" as "01". After ENG-1101 the model is sure of the words; ENG-1102 is not."""
    name = trained()
    d = service.document("B-012", name)
    date = next(f for f in d["fields"] if f["name"] == "statement_date")
    assert date["value"] == "01 Sep 2026" and not date["correct"]
    mine = [w for w in d["words"] if w["id"] in date["word_ids"]]
    assert date["confidence"] == pytest.approx(min(w["p"] * w["confidence"] for w in mine), abs=2e-3)  # the weakest word, OCR included
    assert date["confidence"] < 0.7
