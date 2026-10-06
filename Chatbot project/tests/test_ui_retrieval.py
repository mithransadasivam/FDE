"""The Retrieval tab and the retrieval details in the sidebar (Phase 14)."""
from pathlib import Path

from streamlit.testing.v1 import AppTest

import app.comparison as comparison_module

UI = str(Path(__file__).resolve().parent.parent / "app" / "ui.py")


def row(mode, hit_rate, mrr, answer_seconds, calls=0, behaviour=(10, 10)):
    kinds = {"plain": {"hits": 6, "total": 6}, "reworded": {"hits": 4, "total": 4}, "exact code": {"hits": 4, "total": 4},
             "follow-up": {"hits": 2, "total": 3}, "messy": {"hits": 3, "total": 3}}
    return {"mode": mode, "k": 4, "questions": 20, "hits": round(hit_rate * 20), "hit_rate": hit_rate, "mrr": mrr,
            "by_kind": kinds, "retrieval_ms": 120, "retrieval_model_calls": calls, "calls_per_answer": calls + 1,
            "rerank_fallbacks": 0, "behaviour_correct": behaviour[0], "behaviour_total": behaviour[1],
            "answer_seconds": answer_seconds}


FAKE = [row("vector", 0.95, 0.79, 2.0), row("hybrid", 0.90, 0.87, 2.1), row("rerank", 1.0, 0.94, 4.5, calls=1), row("full", 0.95, 0.91, 6.0, calls=2)]


def saved_result(mode, question):
    return [{"question": question, "searched_for": f"{mode} searched this", "rank": "2", "hit": "True",
             "top_sources": "other.md p.1; vpn_setup_guide.md p.1; x.pdf p.2"}]


def test_empty_state_before_any_comparison(monkeypatch):
    monkeypatch.setattr(comparison_module, "load_comparison", lambda *a, **k: [])
    at = AppTest.from_file(UI, default_timeout=30).run()
    assert not at.exception
    assert any("No retrieval comparison yet" in i.value for i in at.info)


def test_tab_shows_cards_all_four_modes_and_the_chosen_one_highlighted(monkeypatch):
    monkeypatch.setattr(comparison_module, "load_comparison", lambda *a, **k: FAKE)
    monkeypatch.setattr(comparison_module, "load_mode_results", lambda mode, *a, **k: [])
    at = AppTest.from_file(UI, default_timeout=30).run()
    assert not at.exception
    labels = [m.label for m in at.metric]
    assert any(label.startswith("Hit rate @4 (vector)") for label in labels)  # the saved setting is vector
    assert any("gained over vector" in label for label in labels)
    table = [d for d in at.dataframe if "Mode" in d.value.columns][0].value
    assert list(table["Mode"]) == ["✓ vector", "hybrid", "rerank", "full"]
    assert list(table["Meets target"]) == ["yes", "yes", "no", "no"]  # rerank and full take over 3 s per answer


def test_side_by_side_marks_the_expected_document(monkeypatch):
    monkeypatch.setattr(comparison_module, "load_comparison", lambda *a, **k: FAKE)
    monkeypatch.setattr(comparison_module, "load_mode_results", lambda mode, *a, **k: saved_result(mode, "And on a Mac?"))
    at = AppTest.from_file(UI, default_timeout=30).run()
    # pick the follow-up "And on a Mac?" in the question box
    box = [s for s in at.selectbox if s.label == "Question"][0]
    option = [o for o in box.options if "And on a Mac?" in o][0]
    box.select(option).run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "✓ vpn_setup_guide.md p.1" in text and "· other.md p.1" in text
    assert "right chunk at rank 2" in text
    assert any("searched this" in c.value for c in at.caption)


def test_sidebar_shows_mode_test_set_and_decision():
    at = AppTest.from_file(UI, default_timeout=30).run()
    assert not at.exception
    side = " ".join(m.value for m in at.sidebar.markdown) + " ".join(c.value for c in at.sidebar.caption)
    for chip in ("vector", "hybrid", "rerank", "full"):
        assert f'>{chip}</span>' in side
    tables = [t.value for t in at.sidebar.table]
    flat = " ".join(str(v) for t in tables for v in t.to_numpy().ravel())
    assert "retrieval_test_set.csv" in flat and "20 / 20" in flat and "6 · 4 · 4 · 3 · 3" in flat
    assert "Chosen mode" in " ".join(str(i) for t in tables for i in t.index)


def test_unreadable_comparison_file_does_not_crash(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("corrupt")

    monkeypatch.setattr(comparison_module, "load_comparison", boom)
    at = AppTest.from_file(UI, default_timeout=30).run()
    assert not at.exception
    assert any("could not be read" in e.value for e in at.error)
