"""Ticket ENG-302: the bank's proof-of-address rules. 9 tests."""

from fastapi.testclient import TestClient

from app.main import app
from app.prototype.models import Application, Field
from app.prototype.rules import check_policy

APP = Application(case_id="T1", applicant_name="Ananya Mehta", address_line1="Flat 3, 14 Larkspur Row", town="Cheltenham",
                  postcode="GL50 3QR", application_date="2026-07-01", received_date="2026-10-26", channel="app", document="T1.jpg")
RULES = {"max_age_months": 3, "date_counted_from": "received_date", "approved_issuers": ["Lumenvale Energy", "Northmere Bank"]}
LABELS = {"full_name": "Full name", "address": "Address", "statement_date": "Statement date", "issuer": "Issuer"}


def fields(status="ok", **values):
    base = {"full_name": "Ms Ananya R. Mehta", "address": "Flat 3, 14 Larkspur Row, Cheltenham, GL50 3QR",
            "statement_date": "09 Sep 2026", "issuer": "Lumenvale Energy", **values}
    return {k: Field(name=k, label=LABELS[k], value=v, confidence=0.95, status=status) for k, v in base.items()}


def checks(fs, app=APP, rules=RULES):
    return {c.id: c for c in check_policy(fs, app, rules)}


def test_a_clean_document_passes_all_four_in_order():
    out = check_policy(fields(), APP, RULES)
    assert [c.id for c in out] == ["name", "address", "date", "issuer"]
    assert [c.label for c in out] == ["Name matches the application", "Address matches the application",
                                      "Dated within 3 months", "Issuer is on the approved list"]
    assert all(c.status == "pass" and c.detail == "" for c in out)


def test_titles_middle_names_and_initials_are_fine():
    assert checks(fields(full_name="MR A. MEHTA"))["name"].status == "pass"
    c = checks(fields(full_name="Ms Ananya Patel"))["name"]
    assert c.status == "fail"
    assert c.detail == "The document says Ms Ananya Patel; the application says Ananya Mehta"


def test_address_needs_the_same_postcode_and_number():
    assert checks(fields(address="flat 3 14 larkspur row cheltenham gl503qr"))["address"].status == "pass"
    c = checks(fields(address="Flat 8, 14 Larkspur Row, Cheltenham, GL50 3QR"))["address"]
    assert c.status == "fail" and c.detail == "The document shows Flat 8, 14 Larkspur Row, Cheltenham, GL50 3QR"
    assert checks(fields(address="Flat 3, 14 Larkspur Row, Cheltenham, GL50 3QX"))["address"].status == "fail"


def test_date_window_counts_calendar_months_back_from_the_received_date():
    assert checks(fields(statement_date="26 Jul 2026"))["date"].status == "pass"  # exactly 3 months
    c = checks(fields(statement_date="10 Jun 2026"))["date"]
    assert c.status == "fail" and c.detail == "46 days too old (counted from the received date)"


def test_date_after_the_document_arrived_fails():
    c = checks(fields(statement_date="27/10/2026"))["date"]
    assert c.status == "fail" and c.detail == "Dated after the document was received"


def test_the_date_rule_can_count_from_the_application_date():
    c = checks(fields(statement_date="10 Jun 2026"), rules={**RULES, "date_counted_from": "application_date"})["date"]
    assert c.status == "pass"


def test_unreadable_dates_and_unapproved_issuers():
    assert checks(fields(statement_date="Sept the ninth"))["date"].detail == "The date cannot be read as a date"
    c = checks(fields(issuer="Pocketwave Mobile"))["issuer"]
    assert c.status == "fail" and c.detail == "Pocketwave Mobile is not on the approved list"
    assert checks(fields(issuer="NORTHMERE BANK"))["issuer"].status == "pass"


def test_only_ok_or_confirmed_fields_are_used():
    fs = fields()
    fs["statement_date"] = fs["statement_date"].model_copy(update={"status": "check"})
    fs["issuer"] = fs["issuer"].model_copy(update={"status": "confirmed"})
    out = checks(fs)
    assert out["date"].status == "look" and out["date"].detail == "Waiting for a person to confirm the statement date"
    assert out["issuer"].status == "pass"
    assert {c.status for c in checks(fields(status="not_on_page")).values()} == {"look"}


def test_api_applies_the_rules_to_a_case():
    data = TestClient(app).get("/api/cases/D03-007").json()
    c = {x["id"]: x for x in data["checks"]}
    assert c["issuer"]["status"] == "fail" and data["recommendation"] == "fails"
