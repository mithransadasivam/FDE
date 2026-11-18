"""Ticket ENG-601: parse_document() and text_layer_words(). Run: python -m pytest -q tests/test_parse.py"""

import json

import pytest

from app.pipeline import documents as D
from app.pipeline.parse import MIN_TEXT_WORDS, parse_document, text_layer_words


def first(pred):
    return next(r for r in D.manifest("october") if pred(r))


DIGITAL_BILL = first(lambda r: r["file"].endswith(".pdf") and r["kind"] == "utility_bill" and "digital" in r["slices"])
SCANNED_PDF = first(lambda r: r["file"].endswith(".pdf") and "scan" in r["slices"])
JPG = first(lambda r: r["file"].endswith(".jpg"))


def test_a_digital_pdf_is_read_from_its_text_layer():
    p = parse_document(DIGITAL_BILL["doc_id"])
    assert p.source == "text_layer"
    assert p.file == DIGITAL_BILL["file"]
    assert len(p.words) >= MIN_TEXT_WORDS


def test_text_layer_words_have_ids_in_order_and_full_confidence():
    words = text_layer_words(D.document_file(DIGITAL_BILL["doc_id"]))
    assert [w.id for w in words[:3]] == ["w001", "w002", "w003"]
    assert [w.id for w in words] == [f"w{i:03d}" for i in range(1, len(words) + 1)]
    assert all(w.confidence == 1.0 for w in words)


def test_boxes_are_fractions_of_the_page():
    words = text_layer_words(D.document_file(DIGITAL_BILL["doc_id"]))
    for w in words:
        x0, y0, x1, y1 = w.box
        assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1
        assert all(round(v, 4) == v for v in w.box)


def test_words_come_in_reading_order():
    words = text_layer_words(D.document_file(DIGITAL_BILL["doc_id"]))
    assert words[0].text == DIGITAL_BILL["issuer"].split()[0]  # the issuer's name is the first line of a bill
    tops = [w.box[1] for w in words]
    assert all(b >= a - 0.01 for a, b in zip(tops, tops[1:]))  # top to bottom, line by line


def test_the_words_match_what_the_page_says():
    text = " ".join(w.text for w in parse_document(DIGITAL_BILL["doc_id"]).words)
    assert DIGITAL_BILL["issuer"] in text
    assert "Statement date" in text


def test_a_pdf_without_a_text_layer_gives_no_words():
    assert text_layer_words(D.document_file(SCANNED_PDF["doc_id"])) == []


def test_a_scanned_pdf_falls_back_to_the_ocr_file():
    p = parse_document(SCANNED_PDF["doc_id"])
    assert p.source == "ocr"
    assert p.file.endswith(".pdf")
    ocr = json.loads(D.ocr_file(SCANNED_PDF["doc_id"]).read_text(encoding="utf-8"))
    assert [w.model_dump() for w in p.words] == ocr["words"]


def test_a_jpg_scan_is_read_from_the_ocr_file():
    p = parse_document(JPG["doc_id"])
    assert p.source == "ocr" and p.file.endswith(".jpg")
    assert any(w.confidence < 1.0 for w in p.words)


def test_an_unknown_document_raises_key_error():
    with pytest.raises(KeyError):
        parse_document("B-999")


def test_the_whole_batch_parses():
    sources = [parse_document(r["doc_id"]).source for r in D.manifest("october")]
    assert sources.count("text_layer") == 108
    assert sources.count("ocr") == 92
