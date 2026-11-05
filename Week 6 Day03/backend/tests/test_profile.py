"""Ticket ENG-201: profile the client's sample data. 9 tests."""

from fastapi.testclient import TestClient

from app.design.profile import ColumnSpec, profile_column
from app.main import app


def spec(**kw):
    return ColumnSpec(**{"column": "c", **kw})


def test_missing_counts_none_empty_and_spaces():
    p = profile_column(spec(), ["a", None, "", "   ", "b", "c", "d", "e", "f", "g"])
    assert p.rows == 10 and p.missing_pct == 30.0 and p.issues == ["30% missing"]


def test_distinct_counts_present_values_only():
    assert profile_column(spec(), ["x", "x", " y ", None]).distinct == 2


def test_duplicates_only_matter_for_keys():
    assert profile_column(spec(key=True), ["R1", "R2", "R2", "R3", "R3"]).issues == ["2 duplicate values"]
    assert profile_column(spec(), ["R1", "R2", "R2"]).issues == []


def test_invalid_format_percentage_and_examples():
    vals = ["2026-01-01"] * 6 + ["01/02/2026", "3 March", "2026/04/01", "x"]
    p = profile_column(spec(expected="iso_date"), vals)
    assert p.invalid_pct == 40.0
    assert p.bad_examples == ["01/02/2026", "3 March", "2026/04/01"]
    assert p.issues == ["40% not in the expected format"]


def test_one_of_lists_are_checked():
    p = profile_column(spec(expected="one_of:pdf,jpg"), ["pdf"] * 9 + ["heic"])
    assert p.invalid_pct == 10.0


def test_small_problems_are_not_issues():
    p = profile_column(spec(expected="int"), ["1"] * 98 + ["x", None])
    assert p.missing_pct == 1.0 and p.invalid_pct == 1.0 and p.issues == []


def test_undeclared_personal_data_is_found_by_type():
    vals = ["Called on 07700 900123", "email jo@example.com", "sort code 20-11-22 account 41234567", "fine", None]
    p = profile_column(spec(), vals)
    assert p.pii_found == {"phone": 1, "email": 1, "sort_code": 1, "account_number": 1}
    assert p.issues == ["20% missing", "undeclared personal data: phone (1), email (1), sort_code (1), account_number (1)"]


def test_declared_personal_data_is_not_flagged():
    assert profile_column(spec(pii=True), ["07700 900123"]).pii_found == {}


def test_api_profiles_the_sample():
    data = TestClient(app).post("/api/design/profile").json()
    by = {p["column"]: p for p in data["profiles"]}
    assert by["review_id"]["issues"] == ["3 duplicate values"]
    assert by["file_format"]["bad_examples"][0] == "heic"
    assert "undeclared personal data" in by["analyst_notes"]["issues"][-1]
    assert {r["name"]: r["status"] for r in data["readiness"]}["Private"] == "red"
