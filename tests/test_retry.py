"""Tells you when Activity 3 is done: all four tests pass."""

import json

from app.extractor import extract_with_retry
from tests.day05_fakes import FakeClient

GOOD = json.dumps(
    {
        "invoice_number": "CL-88213",
        "vendor_name": "Cloudline Hosting Ltd",
        "invoice_date": "2026-09-03",
        "due_date": "2026-09-17",
        "currency": "USD",
        "line_items": [{"description": "VPS plan", "quantity": 3, "unit_price": 40}],
        "subtotal": 120,
        "tax": 0,
        "total": 120,
    }
)
BAD_TOTAL = GOOD.replace('"total": 120', '"total": 999')
NOT_JSON = "Here is the invoice you asked for!"


def test_valid_first_time_makes_one_call():
    fake = FakeClient(GOOD)
    invoice, error, attempts = extract_with_retry("doc", fake)
    assert invoice is not None and error is None and attempts == 1
    assert len(fake.calls) == 1


def test_invalid_then_valid_succeeds_on_the_retry():
    fake = FakeClient(NOT_JSON, GOOD)
    invoice, _error, attempts = extract_with_retry("doc", fake)
    assert invoice is not None and attempts == 2
    retry_messages = fake.calls[1]["messages"]
    assert [m["role"] for m in retry_messages] == ["user", "assistant", "user"]
    assert retry_messages[1]["content"] == NOT_JSON


def test_retry_message_includes_the_validation_error():
    fake = FakeClient(BAD_TOTAL, GOOD)
    extract_with_retry("doc", fake)
    assert "total" in fake.calls[1]["messages"][2]["content"].lower()


def test_gives_up_after_two_calls():
    fake = FakeClient(NOT_JSON, NOT_JSON, GOOD)
    invoice, error, attempts = extract_with_retry("doc", fake)
    assert invoice is None and error and attempts == 2
    assert len(fake.calls) == 2
