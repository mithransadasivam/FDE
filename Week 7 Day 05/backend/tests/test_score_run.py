"""Ticket ENG-402: score a run against the expert's labels. 8 tests."""

from fastapi.testclient import TestClient

from app.evaluation.metrics import score_run
from app.main import app

LAB = {"c1": {"full_name": "Ms Ananya Mehta", "address": "1 Elm Road, Stroud, GL5 1AA", "statement_date": "09 Sep 2026", "issuer": "Lumenvale Energy"},
       "c2": {"full_name": "Mr Arun Shah & Mrs Priti Shah", "address": "2 Mill Street, Stroud, GL5 2BB", "statement_date": "12 Sep 2026", "issuer": "Harrowgate Water"}}
OUT = {"c1": {"full_name": "MS ANANYA MEHTA", "address": "1 Elm Road Stroud GL5 1AA", "statement_date": "09 Sep 2026", "issuer": "Lumenvale Energy"},
       "c2": {"full_name": "Mr Arun Shah", "address": "2 Mill Street, Stroud, GL5 2BB", "statement_date": "03 Oct 2026", "issuer": "Harrowgate Water"}}
SL = {"c1": ["clean"], "c2": ["two_dates", "joint_names"]}


def test_overall_accuracy():
    s = score_run(OUT, LAB, SL)
    assert (s.overall.correct, s.overall.total, s.overall.accuracy) == (6, 8, 75.0)


def test_case_spaces_and_punctuation_do_not_matter():
    assert score_run({"c1": OUT["c1"]}, LAB, SL).overall.accuracy == 100.0


def test_per_field_in_field_order():
    s = score_run(OUT, LAB, SL)
    assert list(s.per_field) == ["full_name", "address", "statement_date", "issuer"]
    assert s.per_field["full_name"].accuracy == 50.0 and s.per_field["address"].accuracy == 100.0


def test_per_slice_counts_all_four_fields_of_each_case():
    s = score_run(OUT, LAB, SL)
    assert list(s.per_slice) == ["clean", "joint_names", "two_dates"]
    assert (s.per_slice["two_dates"].correct, s.per_slice["two_dates"].total) == (2, 4)
    assert s.per_slice["clean"].accuracy == 100.0


def test_errors_sorted_by_case_then_field():
    s = score_run(OUT, LAB, SL)
    assert [(e.case_id, e.field) for e in s.errors] == [("c2", "full_name"), ("c2", "statement_date")]
    assert s.errors[1].got == "03 Oct 2026" and s.errors[1].expected == "12 Sep 2026"


def test_only_cases_in_both_and_missing_fields_count_as_empty():
    s = score_run({"c1": {"full_name": "Ms Ananya Mehta"}, "zz": {}}, LAB, SL)
    assert s.overall.total == 4 and s.overall.correct == 1


def test_empty_run():
    s = score_run({}, LAB, SL)
    assert (s.overall.total, s.overall.accuracy, s.errors) == (0, 0.0, [])


def test_api_runs_the_prototype_on_the_fifty():
    r = TestClient(app).post("/api/eval/runs", json={"prompt": "extract", "set": "real"}).json()
    assert r["score"]["overall"] == {"correct": 188, "total": 200, "accuracy": 94.0}
    assert r["score"]["per_slice"]["two_dates"]["accuracy"] == 84.4
