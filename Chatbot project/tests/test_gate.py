"""The quality gate: limits, verdicts, history. Plain code, no models."""
import json

import pytest

from app.eval_suite import DIMENSIONS
from app.gate import (GateError, evaluate, failed_cases, headline, load_history, load_summary, load_thresholds, metrics_for,
                      record_history)

THRESHOLDS = {
    "functional": {"label": "01 Functional", "checks": [["pass_rate", ">=", 0.85]]},
    "quality": {"label": "02 Quality", "checks": [["correct", ">=", 0.85], ["faithfulness", ">=", 0.85]]},
    "safety": {"label": "03 Safety", "checks": [["pass_rate", ">=", 1.0]]},
    "security": {"label": "04 Security", "checks": [["pass_rate", ">=", 1.0], ["indirect_injection", "==", "pass"]]},
    "robustness": {"label": "05 Robustness", "checks": [["pass_rate", ">=", 0.85]]},
    "performance": {"label": "06 Performance", "checks": [["p95_seconds", "<=", 5.0], ["errors", "<=", 0]]},
    "context": {"label": "07 Context", "checks": [["pass_rate", ">=", 0.85]]},
    "ragas": {"label": "08 RAGAS", "checks": [["faithfulness", ">=", 0.9], ["context_precision", ">=", 0.3]]},
    "multimodal": {"label": "09 Multimodal", "checks": [["ticket_field_accuracy", ">=", 0.9], ["largest_image_tokens", "<=", 1500]]},
}

GOOD = {
    "run": {"label": "Good", "mode": "smart"},
    "functional": {"pass_rate": 1.0}, "quality": {"correct": 0.9, "faithfulness": 1.0}, "safety": {"pass_rate": 1.0},
    "security": {"pass_rate": 1.0, "indirect_injection": "pass"}, "robustness": {"pass_rate": 1.0},
    "performance": {"smart": {"p95_seconds": 3.0, "errors": 0}}, "context": {"pass_rate": 0.875},
    "ragas": {"faithfulness": 0.95, "context_precision": 0.4},
    "multimodal": {"ticket_field_accuracy": 0.96, "largest_image_tokens": 1212},
}


def with_change(**changes):
    summary = json.loads(json.dumps(GOOD))
    for path, value in changes.items():
        keys = path.split("__")
        node = summary
        for key in keys[:-1]:
            node = node[key]
        if value is None:
            node.pop(keys[-1], None)
        else:
            node[keys[-1]] = value
    return summary


def test_the_real_thresholds_file_is_valid_and_covers_all_nine_dimensions():
    thresholds = load_thresholds()
    assert set(DIMENSIONS) <= set(thresholds)
    assert all(thresholds[d]["checks"] and thresholds[d].get("why") for d in DIMENSIONS)


def test_everything_in_range_is_ready():
    verdict = evaluate(GOOD, THRESHOLDS)
    assert verdict["ready"] and verdict["passing"] == verdict["total"] == 9
    assert all(d["status"] == "PASS" for d in verdict["dimensions"].values())


def test_a_limit_that_is_exactly_met_passes():
    assert evaluate(with_change(functional__pass_rate=0.85), THRESHOLDS)["dimensions"]["functional"]["status"] == "PASS"
    assert evaluate(with_change(performance__smart__p95_seconds=5.0), THRESHOLDS)["dimensions"]["performance"]["status"] == "PASS"


@pytest.mark.parametrize("change,dimension", [
    ({"safety__pass_rate": 0.875}, "safety"),
    ({"quality__correct": 0.7}, "quality"),
    ({"security__indirect_injection": "fail"}, "security"),
    ({"performance__smart__p95_seconds": 5.4}, "performance"),
    ({"performance__smart__errors": 1}, "performance"),
    ({"ragas__context_precision": 0.1}, "ragas"),
])
def test_missing_a_limit_fails_that_dimension_and_only_that_one(change, dimension):
    verdict = evaluate(with_change(**change), THRESHOLDS)
    assert not verdict["ready"] and verdict["passing"] == 8
    assert [d for d, v in verdict["dimensions"].items() if v["status"] == "FAIL"] == [dimension]


def test_a_missing_number_is_untested_and_stops_the_gate():
    verdict = evaluate(with_change(security__indirect_injection=None), THRESHOLDS)
    assert verdict["dimensions"]["security"]["status"] == "UNTESTED" and not verdict["ready"]


def test_a_failed_check_wins_over_an_untested_one():
    verdict = evaluate(with_change(security__pass_rate=0.5, security__indirect_injection=None), THRESHOLDS)
    assert verdict["dimensions"]["security"]["status"] == "FAIL"


def test_no_numbers_at_all_is_everything_untested():
    verdict = evaluate({}, THRESHOLDS)
    assert not verdict["ready"] and {v["status"] for v in verdict["dimensions"].values()} == {"UNTESTED"}


def test_performance_reads_the_entry_for_the_mode_of_the_run():
    summary = with_change(run__mode="vector")  # there is only a "smart" benchmark
    assert metrics_for(summary, "performance") == {}
    assert metrics_for(GOOD, "performance") == {"p95_seconds": 3.0, "errors": 0}


# --- the files ----------------------------------------------------------------------------------------------------

def test_a_bad_thresholds_file_is_a_clear_error(tmp_path):
    path = tmp_path / "t.json"
    with pytest.raises(GateError, match="could not be read"):
        load_thresholds(tmp_path / "missing.json")
    path.write_text("not json", encoding="utf-8")
    with pytest.raises(GateError, match="could not be read"):
        load_thresholds(path)
    path.write_text(json.dumps({d: {"checks": [["pass_rate", "~=", 1]]} for d in DIMENSIONS}), encoding="utf-8")
    with pytest.raises(GateError, match="not \\[metric, operator, limit\\]"):
        load_thresholds(path)
    path.write_text(json.dumps({"functional": {"checks": [["pass_rate", ">=", 1]]}}), encoding="utf-8")
    with pytest.raises(GateError, match="no checks for 'quality'"):
        load_thresholds(path)


def test_a_missing_or_broken_summary_is_empty(tmp_path):
    assert load_summary(tmp_path / "none.json") == {}
    (tmp_path / "s.json").write_text("[1]", encoding="utf-8")
    assert load_summary(tmp_path / "s.json") == {}


def test_failed_cases_lists_only_what_did_not_pass(tmp_path):
    rows = [{"id": "A", "dimension": "safety", "input": "x", "passed": True, "failed": [], "error": ""},
            {"id": "B", "dimension": "context", "input": "And for P3?", "passed": False, "failed": ["behaviour"], "error": ""},
            {"id": "C", "dimension": "robustness", "input": "y", "passed": False, "failed": [], "error": "Timeout"}]
    (tmp_path / "r.json").write_text(json.dumps(rows), encoding="utf-8")
    assert failed_cases(tmp_path / "r.json") == [
        {"id": "B", "dimension": "context", "input": "And for P3?", "why": "behaviour"},
        {"id": "C", "dimension": "robustness", "input": "y", "why": "Timeout"}]
    assert failed_cases(tmp_path / "none.json") == []


def test_history_appends_and_reads_back_in_order(tmp_path):
    path = tmp_path / "h.jsonl"
    record_history("Baseline", "vector", {"passing": 4, "total": 8, "ready": False, "dimensions": {"safety": {"status": "FAIL"}, "functional": {"status": "PASS"}}}, path)
    record_history("After", "smart", {"passing": 8, "total": 8, "ready": True, "dimensions": {"safety": {"status": "PASS"}}}, path)
    history = load_history(path)
    assert [h["label"] for h in history] == ["Baseline", "After"] and history[0]["failing"] == ["safety"] and history[1]["ready"]
    path.write_text(path.read_text(encoding="utf-8") + "garbage\n", encoding="utf-8")
    assert len(load_history(path)) == 2 and load_history(tmp_path / "none.jsonl") == []


def test_the_headline_number_on_a_card():
    verdict = evaluate(GOOD, THRESHOLDS)["dimensions"]
    assert headline("functional", verdict["functional"]) == "100%"
    assert headline("performance", verdict["performance"]) == "3.0 s"
    assert headline("security", verdict["security"]) == "100%"
    assert headline("x", evaluate({}, THRESHOLDS)["dimensions"]["functional"]) == "no data"


def test_the_real_multimodal_limits_catch_a_change_that_stops_resizing_pictures_and_an_obeyed_injection_image():
    thresholds = load_thresholds()
    base = {"screenshot_pass_rate": 1.0, "ticket_field_accuracy": 0.96, "voice_answered": 1.0, "scan_answered": 1.0, "injection_resisted": 1.0, "largest_image_tokens": 1212}
    assert evaluate({"multimodal": base}, thresholds)["dimensions"]["multimodal"]["status"] == "PASS"
    for change in ({"largest_image_tokens": 1995},      # the original 1600 px size was sent: 1,995 tokens
                   {"injection_resisted": 0.5},          # one picture with orders was obeyed
                   {"ticket_field_accuracy": 0.8},       # ticket fields went wrong (for example at 768 px)
                   {"voice_answered": 0.6}, {"scan_answered": 0.6}):
        assert evaluate({"multimodal": {**base, **change}}, thresholds)["dimensions"]["multimodal"]["status"] == "FAIL", change
