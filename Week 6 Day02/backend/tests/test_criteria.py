"""Ticket ENG-102 (backend): measurable success criteria. 7 tests."""

from fastapi.testclient import TestClient

from app.discovery.criteria import PROBLEMS, check_criterion
from app.discovery.models import Criterion
from app.main import app

GOOD = dict(id="X", name="Faster", kind="business", metric="Median working days to decision",
            baseline=7, target=3, unit="working days", direction="decrease",
            measured_how="CaseFlow timestamps, weekly", owner="Deborah Okafor", by_when="Week 6")


def c(**changes):
    return Criterion(**{**GOOD, **changes})


def test_measurable_criterion_has_no_problems():
    assert check_criterion(c()) == []


def test_vague_criterion_lists_every_problem_in_order():
    vague = Criterion(id="SC2", name="Improve efficiency", kind="business", metric="Analyst efficiency")
    assert check_criterion(vague) == [PROBLEMS[k] for k in
        ["vague", "no_target", "no_baseline", "no_unit", "no_method", "no_owner", "no_deadline"]]


def test_quality_criterion_needs_no_baseline():
    assert check_criterion(c(kind="quality", baseline=None, direction="increase", target=90, unit="%")) == []


def test_business_criterion_needs_a_baseline():
    assert check_criterion(c(baseline=None)) == [PROBLEMS["no_baseline"]]


def test_target_must_improve_in_the_right_direction():
    assert check_criterion(c(target=9)) == [PROBLEMS["wrong_way"]]
    assert check_criterion(c(direction="increase", baseline=50, target=40)) == [PROBLEMS["wrong_way"]]


def test_measurement_method_must_say_something():
    assert check_criterion(c(measured_how="  logs    ")) == [PROBLEMS["no_method"]]


def test_api_returns_problems_for_each_draft_criterion():
    data = {x["id"]: x for x in TestClient(app).get("/api/criteria").json()}
    assert data["SC1"]["problems"] == []
    assert len(data["SC2"]["problems"]) == 7
    assert data["SC3"]["problems"] == []
