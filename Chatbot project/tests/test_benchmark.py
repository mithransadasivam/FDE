"""The call log and the benchmark numbers (percentiles, tokens, cost), with fakes and temporary files."""
import json

import pytest

from app import calllog
from app.answer import answer
from app.benchmark import benchmark_questions, cost_usd, percentile, summarize_calls
from app.calllog import log_call, outcome_of, read_log
from app.llm import reset_usage


# --- percentiles --------------------------------------------------------------------------------------------------

def test_percentiles_by_nearest_rank():
    values = list(range(1, 101))  # 1 to 100
    assert percentile(values, 50) == 50 and percentile(values, 95) == 95 and percentile(values, 100) == 100
    assert percentile([3.0, 1.0, 2.0], 50) == 2.0 and percentile([7.0], 95) == 7.0


def test_a_percentile_of_nothing_is_none():
    assert percentile([], 95) is None


def test_p95_means_95_of_100_answers_are_this_fast_or_faster():
    times = [1.0] * 95 + [9.0] * 5
    assert percentile(times, 95) == 1.0 and percentile(times, 96) == 9.0


# --- cost and summary --------------------------------------------------------------------------------------------

def test_cost_from_tokens_and_prices_per_million():
    assert cost_usd(1_000_000, 0, 1.0, 5.0) == 1.0 and cost_usd(0, 1_000_000, 1.0, 5.0) == 5.0
    assert cost_usd(2000, 200, 1.0, 5.0) == pytest.approx(0.003)


def test_the_summary_counts_errors_and_leaves_them_out_of_the_timings():
    rows = [{"seconds": s, "input_tokens": 2000, "output_tokens": 100, "error": ""} for s in (1.0, 2.0, 3.0, 4.0)]
    rows.append({"seconds": None, "input_tokens": 0, "output_tokens": 0, "error": "LLMError"})
    s = summarize_calls(rows, 1.0, 5.0)
    assert (s["calls"], s["errors"], s["p50_seconds"], s["slowest_seconds"]) == (5, 1, 2.0, 4.0)
    assert (s["avg_input_tokens"], s["avg_output_tokens"]) == (2000, 100)
    assert s["cost_per_question_usd"] == pytest.approx(0.0025) and s["cost_per_1000_usd"] == 2.5


def test_a_summary_of_nothing_does_not_crash():
    s = summarize_calls([], 1.0, 5.0)
    assert s["calls"] == 0 and s["p95_seconds"] is None and s["cost_per_question_usd"] == 0


def test_the_benchmark_has_50_answerable_questions_from_the_suite():
    qs = benchmark_questions()
    assert len(qs) == 50 and all(q["expected_behaviour"] == "answer" and q["input"].strip() for q in qs)
    assert {q["dimension"] for q in qs[:28]} == {"quality", "ragas"}


# --- the call log ---------------------------------------------------------------------------------------------------

def test_outcomes():
    assert outcome_of({"refused": True}) == "refused" and outcome_of({"declined": True}) == "declined"
    assert outcome_of({"chunks_used": 0, "sources": []}) == "asked"
    assert outcome_of({"chunks_used": 2, "sources": [{"number": 1}]}) == "answered"


def test_log_call_appends_one_json_line_with_a_time(tmp_path):
    path = tmp_path / "calls.jsonl"
    log_call({"mode": "vector", "seconds": 1.5}, path)
    log_call({"mode": "full", "seconds": 4.0}, path)
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and json.loads(lines[0])["mode"] == "vector" and "time" in json.loads(lines[0])
    assert [r["mode"] for r in read_log(path)] == ["vector", "full"]


def test_reading_a_missing_or_damaged_log_is_safe(tmp_path):
    assert read_log(tmp_path / "nope.jsonl") == []
    path = tmp_path / "bad.jsonl"
    path.write_text('{"mode": "vector"}\nnot json\n', encoding="utf-8")
    assert read_log(path) == [{"mode": "vector"}]


def test_an_unwritable_log_never_breaks_the_chatbot(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    log_call({"mode": "vector"}, blocker / "calls.jsonl")  # the "folder" is a file: writing fails, quietly


def test_tests_never_write_to_the_real_log():
    assert calllog.ENABLED is False


def test_every_answer_is_logged_without_the_question_or_the_answer(tmp_path, monkeypatch):
    monkeypatch.setattr(calllog, "ENABLED", True)
    monkeypatch.setattr(calllog, "LOG_PATH", tmp_path / "calls.jsonl")
    reset_usage()
    chunk = {"text": "Sessions last 12 hours.", "source": "a.md", "page": 1, "score": 0.9}
    answer("How long is a VPN session?", retriever=lambda q, k: [chunk], model=lambda m: "12 hours [1].", mode="rerank")
    (row,) = read_log(tmp_path / "calls.jsonl")
    assert row["mode"] == "rerank" and row["outcome"] == "answered" and row["error"] == "" and row["seconds"] is not None
    text = json.dumps(row)
    assert "How long is a VPN session" not in text and "12 hours" not in text


def test_a_crash_is_logged_as_an_error_and_still_raised(tmp_path, monkeypatch):
    monkeypatch.setattr(calllog, "ENABLED", True)
    monkeypatch.setattr(calllog, "LOG_PATH", tmp_path / "calls.jsonl")

    def boom(q, k):
        raise RuntimeError("down")

    with pytest.raises(RuntimeError):
        answer("How long is a VPN session?", retriever=boom, model=lambda m: "x")
    (row,) = read_log(tmp_path / "calls.jsonl")
    assert row["outcome"] == "error" and row["error"] == "RuntimeError"
