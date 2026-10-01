"""Tells you when Activity 1 is done: all six tests pass."""

import pytest
from pydantic import ValidationError

from app.schemas import Invoice

VALID = {
    "invoice_number": "INV-2026-0412",
    "vendor_name": "Northwind IT Services Pvt Ltd",
    "invoice_date": "2026-09-01",
    "due_date": "2026-10-01",
    "currency": "INR",
    "line_items": [{"description": "Laptop repair", "quantity": 2, "unit_price": 3500}],
    "subtotal": 7000,
    "tax": 1260,
    "total": 8260,
}


def test_a_valid_invoice_passes():
    invoice = Invoice.model_validate(VALID)
    assert invoice.total == 8260 and invoice.invoice_date.year == 2026


def test_due_date_is_optional():
    data = {k: v for k, v in VALID.items() if k != "due_date"}
    assert Invoice.model_validate(data).due_date is None


def test_tax_defaults_to_zero():
    data = {k: v for k, v in VALID.items() if k != "tax"} | {"total": 7000}
    assert Invoice.model_validate(data).tax == 0


def test_currency_must_be_a_three_letter_code():
    with pytest.raises(ValidationError):
        Invoice.model_validate({**VALID, "currency": "$"})


def test_at_least_one_line_item():
    with pytest.raises(ValidationError):
        Invoice.model_validate({**VALID, "line_items": []})


def test_totals_must_add_up():
    with pytest.raises(ValidationError):
        Invoice.model_validate({**VALID, "total": 9999})
