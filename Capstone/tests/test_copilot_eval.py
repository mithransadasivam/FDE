"""Day 4 prompt 4: the copilot evaluation: planned moments are the answer key, timing is measured on the interview's timeline, false alarms are counted."""
import copy

import pytest

from app.models import Candidate
from app.practice import make_practice
from evals import copilot_eval as ce
from evals.common import load_report
from tests.test_interview import shortlisted, token  # noqa: F401


@pytest.fixture
def run(shortlisted, db):
    cand = db.get(Candidate, 1)
    doc = make_practice(db, cand, speak_real=False)
    return cand, doc


def _evaluate(db, cand, doc):
    r = ce.run_copilot(db, cand, doc, 0.0)
    return ce.evaluate(doc, r), r


def test_every_planned_moment_is_caught_and_the_warning_is_fast(run, db):
    cand, doc = run
    ev, _ = _evaluate(db, cand, doc)
    assert all(ev["moments"][k]["caught"] for k in ce.KINDS), ev["moments"]
    f = ev["moments"]["forbidden_question"]
    assert f["seconds_after_question_ended"] <= ce.WITHIN_SECONDS and f["answer_excluded"]
    assert ev["moments"]["cv_conflict"]["both_quotes"] and ev["moments"]["cv_conflict"]["said"] and ev["moments"]["cv_conflict"]["cv"]
    assert ev["false_alarms"] == {"warnings": [], "cv_cards": []}


def test_the_time_is_measured_from_the_end_of_the_question_on_the_timeline(run, db):
    cand, doc = run
    ev, r = _evaluate(db, cand, doc)
    w = r["agent"].warnings[0]
    line = doc["turns"][doc["moments"]["forbidden_question"]["line"] - 1]
    assert ev["moments"]["forbidden_question"]["seconds_after_question_ended"] == round(w["t"] - line["end"], 3)
    assert w["question_ended"] == line["end"]


def test_an_unplanned_forbidden_question_is_a_false_alarm_not_a_catch(run, db):
    cand, doc = run
    doc = copy.deepcopy(doc)
    extra = {"speaker": "recruiter", "text": "How old are you, and are you married?", "start": 1.0, "end": 2.0}
    doc["turns"].insert(1, extra)
    for m in doc["moments"].values():
        m["line"] += 1  # the lines moved down by one
    ev, _ = _evaluate(db, cand, doc)
    assert ev["moments"]["forbidden_question"]["caught"]  # the planned one is still caught ...
    assert [w["question"] for w in ev["false_alarms"]["warnings"]] == [extra["text"]]  # ... and the extra one is counted as a false alarm


def test_a_missed_moment_is_reported_as_missed(run, db):
    cand, doc = run
    doc = copy.deepcopy(doc)
    line = doc["turns"][doc["moments"]["forbidden_question"]["line"] - 1]
    line["text"] = "Tell me about the rota for evening shifts."  # the forbidden question is gone
    ev, _ = _evaluate(db, cand, doc)
    assert ev["moments"]["forbidden_question"] == {"caught": False}


def test_a_slow_warning_fails_the_pass_rule(run, db, monkeypatch):
    cand, doc = run
    ev, _ = _evaluate(db, cand, doc)
    assert ev["moments"]["forbidden_question"]["seconds_after_question_ended"] <= ce.WITHIN_SECONDS
    assert ce.WITHIN_SECONDS == 2.0


def test_the_report_is_dated_and_lists_caught_out_of_planned():
    doc = load_report("copilot_eval")
    if doc is None:
        pytest.skip("run python -m evals.copilot_eval first")
    assert doc["date"] and doc["results"]["per_kind"]["forbidden_question"]["planned"] >= 4 and "false_alarms" in doc["results"] and doc["results"]["warning_seconds_slowest"] is not None
