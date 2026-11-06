"""Fixes from the Day 3 headless review: the address rule and the named analyst."""

from fastapi.testclient import TestClient

from app.main import app
from app.prototype.models import Application, Field
from app.prototype.rules import all_numbers, check_policy, load_rules

APPLICATION = Application(case_id="T-1", applicant_name="Ananya Mehta", address_line1="Flat 3, 14 Larkspur Row", town="Cheltenham",
                          postcode="GL50 3QR", application_date="2026-09-01", received_date="2026-09-10", channel="web", document="x.jpg")


def address_check(value: str):
    field = Field(name="address", label="Address", value=value, confidence=0.99, status="ok")
    checks = check_policy({"address": field}, APPLICATION, load_rules())
    return next(c for c in checks if c.id == "address")


def test_numbers_ignore_the_postcode():
    assert all_numbers("Flat 3, 14 Larkspur Row, Cheltenham GL50 3QR") == ["3", "14"]


def test_the_same_flat_in_another_house_fails_the_address():
    assert address_check("Flat 3, 14 Larkspur Row, Cheltenham GL50 3QR").status == "pass"
    assert address_check("Flat 3, 99 Other Road, Cheltenham GL50 3QR").status == "fail"


def test_an_unknown_analyst_cannot_decide():
    r = TestClient(app).post("/api/cases/D03-002/decision", json={"decision": "approve", "analyst_id": "nobody"})
    assert r.status_code == 403
