"""Smoke tests for the Streamlit app, run headlessly with a fake answer function."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import app.answer as answer_module

UI = str(Path(__file__).resolve().parent.parent / "app" / "ui.py")


def fake_result(declined):
    return {
        "answer": "I don't know: ..." if declined else "Backups are kept 30 days [1].",
        "sources": [] if declined else [{"number": 1, "source": "backup.md", "page": 1, "text": "t", "score": 0.8}],
        "declined": declined, "best_score": 0.8, "chunks_used": 1, "seconds": 0.1, "reason": "",
    }


def test_app_loads_with_three_tabs():
    at = AppTest.from_file(UI, default_timeout=30).run()
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Chat", "Knowledge base", "Test results", "Retrieval"]


@pytest.mark.parametrize("declined", [False, True])
def test_chat_shows_answer_or_declined_badge(monkeypatch, declined):
    monkeypatch.setattr(answer_module, "answer", lambda q, **kw: fake_result(declined))
    at = AppTest.from_file(UI, default_timeout=30).run()
    at.chat_input[0].set_value("How long are backups kept?").run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert ("DECLINED" in text) is declined
    assert ("backup.md" in text) is (not declined)


def test_missing_index_shows_friendly_message(monkeypatch):
    def boom(q, **kw):
        raise ValueError("no index")

    monkeypatch.setattr(answer_module, "answer", boom)
    at = AppTest.from_file(UI, default_timeout=30).run()
    at.chat_input[0].set_value("hello").run()
    assert not at.exception
    assert any("isn't built yet" in e.value for e in at.error)


def test_test_results_tab_shows_summary_and_failure(monkeypatch):
    import app.evaluate as evaluate

    row = {"number": 3, "question": "My VPN drops", "expected": "Use TCP", "should_answer": True,
           "behaviour": "declined", "ok": False, "answer": "I don't know", "sources": "",
           "seconds": 2.0, "best_score": 0.53, "reason": "guard 1: best score below minimum"}
    ok_row = dict(row, number=1, behaviour="answered", ok=True, sources="[1] a.md p.1", reason="")
    run = {"run": 1, "min_score": 0.6, "note": "tuning", "time": "2026-10-01T22:00:00",
           "summary": {"total": 2, "behaviour_correct": 1, "should_answer": 2, "answered_correctly": 1,
                       "should_decline": 0, "declined_correctly": 0, "avg_seconds": 2.0},
           "rows": [ok_row, row]}
    monkeypatch.setattr(evaluate, "load_runs", lambda *a, **k: [run])
    at = AppTest.from_file(UI, default_timeout=30).run()
    assert not at.exception
    assert [m.value for m in at.metric][0] == "1 / 2"
    assert any("Question 3" in e.value for e in at.error)
    assert at.dataframe  # results table is shown


def test_unexpected_error_shows_friendly_message_not_a_traceback(monkeypatch):
    def boom(q, **kw):
        raise KeyError("some chroma problem at D:/secret/path")

    monkeypatch.setattr(answer_module, "answer", boom)
    at = AppTest.from_file(UI, default_timeout=30).run()
    at.chat_input[0].set_value("hello").run()
    assert not at.exception
    assert any("couldn't reach the answer service" in e.value for e in at.error)
    assert not any("secret" in e.value for e in at.error)


def test_model_markdown_links_and_images_are_not_rendered(monkeypatch):
    evil = {"answer": "See ![x](https://evil.example/p.png?q=1) and [Reset](https://evil.example) [1].",
            "sources": [{"number": 1, "source": "a.md", "page": 1, "text": "t", "score": 0.8}],
            "declined": False, "best_score": 0.8, "chunks_used": 1, "seconds": 0.1, "reason": ""}
    monkeypatch.setattr(answer_module, "answer", lambda q, **kw: evil)
    at = AppTest.from_file(UI, default_timeout=30).run()
    at.chat_input[0].set_value("q").run()
    assert not at.exception
    shown = [m.value for m in at.markdown if "evil.example" in m.value]
    import re

    assert shown and not any(re.search(r"(?<!\\)[\[\]]", v) for v in shown)  # all brackets escaped


def test_chat_input_has_a_length_limit():
    at = AppTest.from_file(UI, default_timeout=30).run()
    assert at.chat_input[0].proto.max_chars == 500


# ---- look and feel (recommendations 1-5 and 7) ----
def test_empty_chat_shows_welcome_and_three_examples():
    at = AppTest.from_file(UI, default_timeout=30).run()
    assert not at.exception
    assert any("I answer IT questions" in m.value for m in at.markdown)
    examples = [b for b in at.button if b.key and b.key.startswith("example_")]
    assert len(examples) == 3


def test_clicking_an_example_asks_that_question_and_hides_the_examples(monkeypatch):
    asked = []

    def fake(q, **kw):
        asked.append(q)
        return fake_result(False)

    monkeypatch.setattr(answer_module, "answer", fake)
    at = AppTest.from_file(UI, default_timeout=30).run()
    at.button(key="example_1").click().run()
    assert not at.exception
    assert asked == ["How long do you keep daily server backups?"]
    assert not [b for b in at.button if b.key and b.key.startswith("example_")]


def test_clear_chat_button_empties_the_conversation(monkeypatch):
    monkeypatch.setattr(answer_module, "answer", lambda q, **kw: fake_result(False))
    at = AppTest.from_file(UI, default_timeout=30).run()
    clear = [b for b in at.sidebar.button if "Clear chat" in b.label][0]
    assert clear.disabled  # nothing to clear yet
    at.chat_input[0].set_value("hello").run()
    clear = [b for b in at.sidebar.button if "Clear chat" in b.label][0]
    assert not clear.disabled
    clear.click().run()
    assert not at.exception
    assert any("I answer IT questions" in m.value for m in at.markdown)  # back to the welcome screen


def test_sidebar_uses_friendly_name_and_tables_have_real_headers():
    at = AppTest.from_file(UI, default_timeout=30).run()
    side = " ".join(m.value for m in at.sidebar.markdown)
    assert "Northwind IT docs" in side


# ---- follow-ups use the real chat history (Phase 13) ----
def test_the_previous_question_comes_from_the_chat_history_and_searched_for_is_shown(monkeypatch):
    seen = []

    def fake(q, previous_question="", **kw):
        seen.append((q, previous_question))
        return {**fake_result(False), "searched_for": f"rewritten: {q}"}

    monkeypatch.setattr(answer_module, "answer", fake)
    at = AppTest.from_file(UI, default_timeout=30).run()
    at.chat_input[0].set_value("How do I install the VPN client on Windows?").run()
    at.chat_input[0].set_value("And on a Mac?").run()
    assert not at.exception
    assert seen == [("How do I install the VPN client on Windows?", ""),
                    ("And on a Mac?", "How do I install the VPN client on Windows?")]
    captions = [c.value for c in at.caption]
    assert any(c.startswith("Searched for: rewritten: And on a Mac?") for c in captions)


def test_clearing_the_chat_forgets_the_previous_question(monkeypatch):
    seen = []

    def fake(q, previous_question="", **kw):
        seen.append(previous_question)
        return fake_result(False)

    monkeypatch.setattr(answer_module, "answer", fake)
    at = AppTest.from_file(UI, default_timeout=30).run()
    at.chat_input[0].set_value("first question").run()
    [b for b in at.sidebar.button if "Clear chat" in b.label][0].click().run()
    at.chat_input[0].set_value("And on a Mac?").run()
    assert seen == ["", ""]
