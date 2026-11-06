"""Day 4 files are in place. These pass from the start of Day 4. 6 tests."""

from fastapi.testclient import TestClient

from app.evaluation.service import labelling_items, real_cases, taxonomy, tom_tags
from app.main import app

c = TestClient(app)


def test_fifty_labelled_cases_with_slices():
    cases = real_cases()
    assert len(cases) == 50 and sum(1 for v in cases.values() if "two_dates" in v["slices"]) == 8


def test_twenty_items_to_label():
    assert len(labelling_items()) == 20
    assert c.get("/api/eval/labelling").json()["guideline_version"] == "v0 (data/)"


def test_taxonomy_is_a_pareto_table():
    t = taxonomy({"a": "x", "b": "y", "c": "x", "d": ""})
    assert t == [{"type": "x", "count": 2, "share": 66.7, "cumulative": 66.7}, {"type": "y", "count": 1, "share": 33.3, "cumulative": 100.0}]


def test_tom_tagged_sixteen_failures():
    assert len(tom_tags()) == 16


def test_judge_prompts_are_found():
    j = c.get("/api/eval/judges").json()["judges"]
    assert [x["judge"] for x in j] == ["wrong_date", "incomplete_name"] and "wrong_date" in j[0]["prompts"]


def test_synthetic_cases_are_written():
    made = c.post("/api/eval/synthetic", json={"slice": "two_dates", "n": 5}).json()["made"]
    assert made == ["S-001", "S-002", "S-003", "S-004", "S-005"]
    assert len(c.get("/api/eval/synthetic").json()) == 5
