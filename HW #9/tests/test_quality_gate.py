"""Tells you when Activity 3 is done: all five tests pass. No model is used."""

import pytest

from app.quality_gate import quality_gate

SUMMARY = {"hit_rate": 0.9, "judge_correct_rate": 0.75, "avg_seconds": 3.2}


def test_a_summary_that_meets_every_threshold_passes():
    assert quality_gate(SUMMARY, {"min_hit_rate": 0.85, "max_avg_seconds": 5}) == []


def test_a_minimum_that_is_not_met_is_reported():
    assert quality_gate(SUMMARY, {"min_judge_correct_rate": 0.8}) == [
        "judge_correct_rate is 0.75, needs >= 0.8"
    ]


def test_a_maximum_that_is_exceeded_is_reported_and_equal_values_pass():
    assert quality_gate(SUMMARY, {"max_avg_seconds": 3}) == [
        "avg_seconds is 3.2, needs <= 3"
    ]
    assert quality_gate(SUMMARY, {"min_hit_rate": 0.9, "max_avg_seconds": 3.2}) == []


def test_a_missing_metric_fails_and_problems_keep_the_thresholds_order():
    problems = quality_gate(SUMMARY, {"min_mrr": 0.5, "min_judge_correct_rate": 0.8})
    assert problems == ["mrr is missing", "judge_correct_rate is 0.75, needs >= 0.8"]


def test_an_unknown_threshold_name_raises():
    with pytest.raises(ValueError):
        quality_gate(SUMMARY, {"hit_rate": 0.9})
