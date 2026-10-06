import json

import pytest

from app.comparison import build_row, load_comparison, meets_target, save_comparison
from app.retrieval_eval import run_eval

RIGHT = {"source": "a.md", "text": "kept for 30 days", "page": 1}
WRONG = {"source": "a.md", "text": "something else", "page": 1}


def rows_for(retrieve):
    test_set = [
        {"question": "q1", "previous_question": "", "kind": "plain", "expected_source": "a.md", "evidence": "kept for 30 days"},
        {"question": "q2", "previous_question": "q1", "kind": "follow-up", "expected_source": "a.md", "evidence": "kept for 30 days"},
    ]
    return run_eval(test_set, retrieve, k=4)


def behaviour(ok_flags, seconds):
    return [{"ok": ok, "seconds": s} for ok, s in zip(ok_flags, seconds)]


def test_row_has_scores_cost_and_behaviour():
    row = build_row("rerank", 4, rows_for(lambda r: [RIGHT] if r["kind"] == "plain" else [WRONG]),
                    behaviour([True, True, False], [2.0, 4.0, 3.0]))
    assert (row["mode"], row["questions"], row["hits"], row["hit_rate"]) == ("rerank", 2, 1, 0.5)
    assert row["by_kind"] == {"plain": {"hits": 1, "total": 1}, "follow-up": {"hits": 0, "total": 1}}
    assert (row["retrieval_model_calls"], row["calls_per_answer"]) == (1, 2)
    assert (row["behaviour_correct"], row["behaviour_total"], row["answer_seconds"]) == (2, 3, 3.0)


def test_without_a_behaviour_run_the_answer_time_is_unknown():
    row = build_row("vector", 4, rows_for(lambda r: [RIGHT]))
    assert row["answer_seconds"] is None and row["behaviour_correct"] is None
    assert (row["retrieval_model_calls"], row["calls_per_answer"]) == (0, 1)


@pytest.mark.parametrize("hit_rate,seconds,expected", [
    (0.95, 2.0, True), (0.90, 3.0, True),     # exactly on the target counts
    (0.85, 2.0, False), (1.0, 3.5, False), (0.95, None, False),
])
def test_meets_target_needs_both_accuracy_and_the_whole_answer_time(hit_rate, seconds, expected):
    assert meets_target({"hit_rate": hit_rate, "answer_seconds": seconds}, 0.90, 3.0) is expected


def test_save_and_load_round_trip_with_flat_csv(tmp_path):
    row = build_row("vector", 4, rows_for(lambda r: [RIGHT]), behaviour([True], [2.0]))
    save_comparison([row], tmp_path / "c.json", tmp_path / "c.csv")
    assert load_comparison(tmp_path / "c.json") == [row]
    header, first = (tmp_path / "c.csv").read_text(encoding="utf-8").splitlines()[:2]
    assert "plain" in header and "answer_seconds" in header and "1/1" in first


def test_load_comparison_handles_missing_broken_and_incomplete_files(tmp_path):
    assert load_comparison(tmp_path / "nope.json") == []
    (tmp_path / "bad.json").write_text("not json", encoding="utf-8")
    assert load_comparison(tmp_path / "bad.json") == []
    (tmp_path / "odd.json").write_text(json.dumps([{"mode": "x"}, 5]), encoding="utf-8")
    assert load_comparison(tmp_path / "odd.json") == []
    (tmp_path / "shape.json").write_text(json.dumps({"mode": "x"}), encoding="utf-8")
    assert load_comparison(tmp_path / "shape.json") == []


def test_evaluation_records_what_was_searched_for():
    def retrieve(row):
        return {"chunks": [RIGHT], "searched_for": "rewritten " + row["question"]}

    results = rows_for(retrieve)
    assert [r["searched_for"] for r in results] == ["rewritten q1", "rewritten q2"] and results[0]["hit"]
    assert rows_for(lambda r: [RIGHT])[0]["searched_for"] == "q1"  # plain list: the question as typed
