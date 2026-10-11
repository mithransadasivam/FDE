"""The Evaluation tab: nine cards, the verdict, the failures, and the sidebar sections."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import app.gate as gate_module
from app.eval_suite import DIMENSIONS

UI = str(Path(__file__).resolve().parent.parent / "app" / "ui.py")

THRESHOLDS = {d: {"label": f"0{n} {d.title()}", "checks": [["pass_rate", ">=", 0.85]], "why": f"why {d}"} for n, d in enumerate(DIMENSIONS, start=1)}
THRESHOLDS["performance"]["checks"] = [["p95_seconds", "<=", 5.0], ["errors", "<=", 0]]
THRESHOLDS["quality"]["checks"] = [["correct", ">=", 0.85]]
THRESHOLDS["ragas"]["checks"] = [["faithfulness", ">=", 0.9], ["context_precision", ">=", 0.3]]
THRESHOLDS["multimodal"]["checks"] = [["ticket_field_accuracy", ">=", 0.9], ["largest_image_tokens", "<=", 1500]]
SUMMARY = {
    "run": {"label": "Test run", "mode": "smart", "cases": 75}, "judge": {"agreement_correct": "10/10", "agreement_faithful": "10/10"},
    "functional": {"pass_rate": 1.0}, "quality": {"correct": 0.9}, "safety": {"pass_rate": 1.0}, "security": {"pass_rate": 1.0},
    "robustness": {"pass_rate": 1.0}, "performance": {"smart": {"p95_seconds": 3.0, "errors": 0}}, "context": {"pass_rate": 0.875},
    "ragas": {"faithfulness": 0.95, "context_precision": 0.4}, "multimodal": {"ticket_field_accuracy": 0.96, "largest_image_tokens": 1212},
}


def run_app(monkeypatch, summary=SUMMARY, thresholds=THRESHOLDS, failures=(), history=()):
    monkeypatch.setattr(gate_module, "load_summary", lambda *a, **k: summary)
    monkeypatch.setattr(gate_module, "load_thresholds", lambda *a, **k: thresholds)
    monkeypatch.setattr(gate_module, "failed_cases", lambda *a, **k: list(failures))
    monkeypatch.setattr(gate_module, "load_history", lambda *a, **k: list(history))
    at = AppTest.from_file(UI, default_timeout=30).run()
    assert not at.exception
    return at


def tab_text(at):
    evaluation = [t for t in at.tabs if t.label == "Evaluation"][0]
    return " ".join(m.value for m in evaluation.markdown) + " " + " ".join(c.value for c in evaluation.caption)


def test_all_nine_cards_are_shown_with_their_status(monkeypatch):
    at = run_app(monkeypatch)
    text = tab_text(at)
    for dimension in DIMENSIONS:
        assert THRESHOLDS[dimension]["label"] in text, dimension
    assert text.count("PASS") == 9 and "FAIL" not in text
    assert "100%" in text and "3.0 s" in text and "88%" in text  # headline numbers (88% is Context: 7 of 8 conversations)


def test_the_verdict_says_ready_when_everything_passes(monkeypatch):
    at = run_app(monkeypatch)
    assert any("Ready to ship" in s.value for s in at.success) and not at.error


def test_the_verdict_names_the_failing_dimensions(monkeypatch):
    broken = {**SUMMARY, "safety": {"pass_rate": 0.5}}
    at = run_app(monkeypatch, summary=broken)
    assert any("Not ready to ship" in e.value and "03 Safety" in e.value for e in at.error)
    assert tab_text(at).count("FAIL") == 1


def test_a_missing_number_shows_untested(monkeypatch):
    partial = {k: v for k, v in SUMMARY.items() if k != "ragas"}
    at = run_app(monkeypatch, summary=partial)
    assert "UNTESTED" in tab_text(at) and any("Not ready" in e.value for e in at.error)


def test_failed_cases_are_listed_with_the_reason(monkeypatch):
    at = run_app(monkeypatch, failures=[{"id": "CTX-03", "dimension": "context", "input": "Is that the same?", "why": "behaviour"}])
    tables = [d.value for d in at.dataframe if "Why it failed" in d.value.columns]
    assert tables and list(tables[0]["Case"]) == ["CTX-03"] and list(tables[0]["Why it failed"]) == ["behaviour"]


def test_no_failures_says_so(monkeypatch):
    assert "Every case of the last full run passed" in tab_text(run_app(monkeypatch))


def test_before_any_evaluation_the_tab_explains_how_to_start(monkeypatch):
    at = run_app(monkeypatch, summary={})
    assert any("No evaluation yet" in i.value for i in at.info)


def test_an_unreadable_thresholds_file_is_a_friendly_error(monkeypatch):
    def boom(*a, **k):
        raise gate_module.GateError("bad")

    monkeypatch.setattr(gate_module, "load_summary", lambda *a, **k: SUMMARY)
    monkeypatch.setattr(gate_module, "load_thresholds", boom)
    monkeypatch.setattr(gate_module, "load_history", lambda *a, **k: [])
    monkeypatch.setattr(gate_module, "failed_cases", lambda *a, **k: [])
    at = AppTest.from_file(UI, default_timeout=30).run()
    assert not at.exception and any("could not be read" in e.value for e in at.error)


def test_the_sidebar_shows_the_run_the_gate_and_the_history(monkeypatch):
    history = [{"label": "Baseline", "passing": 4, "total": 8}, {"label": "After fixes", "passing": 7, "total": 8}]
    at = run_app(monkeypatch, history=history)
    tables = " ".join(str(v) for t in at.sidebar.table for v in t.value.to_numpy().ravel())
    for expected in ("eval_suite.csv", "75", "smart", "10/10 · 10/10", "eval_thresholds.json", "9 / 9", "READY"):
        assert expected in tables, expected
    captions = " ".join(c.value for c in at.sidebar.caption)
    assert "Baseline" in captions and "After fixes" in captions and "7 / 8" in captions


def test_the_sidebar_gate_says_not_ready_when_a_dimension_fails(monkeypatch):
    at = run_app(monkeypatch, summary={**SUMMARY, "functional": {"pass_rate": 0.1}})
    tables = " ".join(str(v) for t in at.sidebar.table for v in t.value.to_numpy().ravel())
    assert "8 / 9" in tables and "NOT READY" in tables


def test_text_from_a_result_file_cannot_inject_html_into_a_card(monkeypatch):
    nasty = {d: dict(v) for d, v in THRESHOLDS.items()}
    nasty["safety"]["label"] = "03 <script>alert(1)</script>"
    at = run_app(monkeypatch, thresholds=nasty)
    assert "<script>" not in tab_text(at)
