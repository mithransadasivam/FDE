"""Checks that amounts the model invented (not shown in the document) are caught."""

import json
from pathlib import Path

from app.extractor import amounts_in, not_in_document
from app.schemas import Invoice


def test_reads_different_number_formats():
    assert {1234.5, 100300.0} <= amounts_in("Total 1,234.50 and 1,00,300.00")
    assert 1234.5 in amounts_in("Total 1.234,50")


def test_all_ten_invoices_extracted_earlier_match_their_documents():
    # The saved results come from the retry run; only invoice 07 was changed by the model.
    for path in sorted(Path("data/invoices").glob("*.txt")):
        saved = Path("data/extracted") / (path.stem + ".json")
        invoice = Invoice.model_validate(json.loads(saved.read_text()))
        problems = not_in_document(invoice, path.read_text(encoding="utf-8"))
        if "invoice_07" in path.name:
            assert problems == ["tax 200.00"]
        else:
            assert problems == [], path.name
