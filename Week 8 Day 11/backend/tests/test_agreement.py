"""Ticket ENG-401: agreement between two raters, with Cohen's kappa. 9 tests."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.evaluation.metrics import agreement
from app.evaluation.service import tom_sample_labels
from app.main import app

FIX = Path(__file__).parent / "fixtures"


def test_perfect_agreement():
    a = agreement({"1": "wrong", "2": "correct"}, {"1": "wrong", "2": "correct"}, "wrong")
    assert (a.n, a.agree, a.percent, a.kappa) == (2, 2, 100.0, 1.0)
    assert (a.tp, a.fp, a.fn, a.tn) == (1, 0, 0, 1) and a.disagreements == []


def test_kappa_corrects_for_chance():
    # 75% agreement, but most of it is "correct" vs "correct": kappa is low
    rater = {f"i{k}": "correct" for k in range(20)} | {"i0": "wrong", "i1": "wrong", "i2": "wrong"}
    expert = {f"i{k}": "correct" for k in range(20)} | {"i0": "wrong", "i1": "wrong", "i3": "wrong", "i4": "wrong", "i5": "wrong", "i6": "wrong"}
    a = agreement(rater, expert, "wrong")
    assert (a.agree, a.percent, a.kappa) == (15, 75.0, 0.31)
    assert (a.tp, a.fp, a.fn, a.tn) == (2, 1, 4, 13)


def test_caught_and_cleared():
    a = agreement({"a": "fail", "b": "pass", "c": "fail", "d": "pass"}, {"a": "fail", "b": "fail", "c": "pass", "d": "pass"}, "fail")
    assert (a.caught, a.cleared) == (0.5, 0.5)
    assert a.disagreements == ["b", "c"]


def test_only_items_both_labelled_count():
    a = agreement({"a": "wrong", "b": "correct", "x": "wrong"}, {"a": "wrong", "b": "correct", "y": "correct"}, "wrong")
    assert a.n == 2 and a.agree == 2


def test_any_other_label_is_negative():
    a = agreement({"a": "pass", "b": "unsure"}, {"a": "ok", "b": "pass"}, "fail")
    assert a.agree == 2 and a.tn == 2 and a.caught is None


def test_one_label_for_everything():
    assert agreement({"a": "pass", "b": "pass"}, {"a": "pass", "b": "pass"}, "fail").kappa == 1.0
    assert agreement({"a": "fail", "b": "fail"}, {"a": "pass", "b": "pass"}, "fail").kappa == 0.0


def test_nothing_in_common():
    a = agreement({"a": "fail"}, {"b": "fail"}, "fail")
    assert (a.n, a.percent, a.kappa, a.caught, a.cleared) == (0, 0.0, 0.0, None, None)


def test_the_class_labels_before_and_after_the_guidelines():
    tom = tom_sample_labels()
    before = agreement(json.loads((FIX / "labels_student_v0.json").read_text()), tom, "wrong")
    after = agreement(json.loads((FIX / "labels_student_v1.json").read_text()), tom, "wrong")
    assert (before.percent, before.kappa) == (75.0, 0.31)
    assert (after.percent, after.kappa) == (95.0, 0.87)


def test_api_calibrates_a_judge():
    r = TestClient(app).post("/api/eval/judges/wrong_date/run").json()["agreement"]
    assert (r["tp"], r["fp"], r["fn"], r["tn"], r["kappa"]) == (4, 2, 1, 43, 0.69)
