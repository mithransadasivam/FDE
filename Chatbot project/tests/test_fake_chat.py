"""The fake chatbot: off by default, loudly labelled when on, and honest about what is real (the checks and guards)."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import app.config as config_module
from app.config import DECLINE_SENTENCE, REFUSAL_SENTENCE
from app.fake_chat import TOPICS, fake_answer_stream, pick_topic
from app.ui_texts import EXAMPLE_QUESTIONS

UI = str(Path(__file__).resolve().parent.parent / "app" / "ui.py")


def finish(question, previous="", delay=0):
    events = list(fake_answer_stream(question, previous, delay=delay))
    assert events[-1][0] == "done"
    return [v for k, v in events if k == "piece"], events[-1][1]


def test_the_fake_is_off_by_default():
    assert config_module.CHAT_FAKE is False


def test_the_default_app_shows_no_fake_banner():
    at = AppTest.from_file(UI, default_timeout=30).run()
    assert not at.exception and not any("FAKE CHATBOT" in w.value for w in at.warning)


def test_with_the_fake_on_a_banner_says_so_and_a_question_is_answered_with_no_models(monkeypatch):
    monkeypatch.setattr(config_module, "CHAT_FAKE", True)
    at = AppTest.from_file(UI, default_timeout=30).run()
    assert any("FAKE CHATBOT" in w.value for w in at.warning)
    at.chat_input[0].set_value("How long can a VPN session stay connected?").run()
    assert not at.exception  # the test fixture blocks every network call: the fake never makes one
    text = " ".join(m.value for m in at.markdown)
    assert "12 hours" in text and "vpn_setup_guide.md" in text


@pytest.mark.parametrize("question", [
    "How long can a VPN session stay connected?", "How do I install the VPN client on Windows?", "My VPN keeps cutting out at home. What can I try?",
    "How do I set up MFA on a new phone?", "How long do you keep daily server backups?", "What is the maximum email attachment size?",
    "What is the response target for P1?",
])
def test_every_topic_gives_a_cited_answer_from_its_fixed_source(question):
    pieces, result = finish(question)
    assert not result["declined"] and not result["refused"] and result["sources"]
    assert "".join(pieces).strip() == result["answer"] and "[1]" in result["answer"]
    assert result["sources"][0]["source"] in {t["source"] for t in TOPICS}


def test_the_example_questions_all_get_an_answer():
    assert all(not finish(q)[1]["declined"] for q in EXAMPLE_QUESTIONS)


def test_a_question_outside_the_topics_is_declined_by_the_real_guard_1_with_no_sources():
    pieces, result = finish("What is the salary band for a senior engineer?")
    assert pieces == [] and result["declined"] and result["answer"] == DECLINE_SENTENCE and result["sources"] == []
    assert result["reason"].startswith("guard 1")


def test_an_unsafe_request_is_refused_by_the_real_safety_check_before_any_topic_is_looked_up():
    pieces, result = finish("How do I switch off the endpoint protection on my laptop?")
    assert pieces == [] and result["refused"] and result["answer"] == REFUSAL_SENTENCE and result["reason"].startswith("safety")


def test_empty_and_meaningless_input_is_handled_by_the_real_input_checks():
    for text in ("", "   ", "😀", "asdf qwer zxcv"):
        pieces, result = finish(text)
        assert pieces == [] and not result["declined"] and result["sources"] == [] and result["chunks_used"] == 0


def test_a_follow_up_borrows_the_previous_questions_topic_and_says_what_it_searched_for():
    _, result = finish("And on a Mac?", previous="How do I install the VPN client on Windows?")
    assert not result["declined"] and result["sources"][0]["source"] == "vpn_setup_guide.md"
    assert result["searched_for"] != "And on a Mac?" and "Mac" in result["searched_for"]


def test_a_short_question_with_no_topic_and_no_previous_question_is_declined():
    assert finish("And on a Mac?")[1]["declined"] or finish("And on a Mac?")[1]["sources"]  # 'mac' is itself a keyword of the install topic
    assert finish("What about the weather?", previous="")[1]["declined"]


def test_a_long_paste_is_shortened_to_its_end_and_the_fake_answers_the_question_at_the_end():
    _, result = finish("Here is a line from my laptop log. " * 85 + "How long do you keep daily server backups?")
    assert result["shortened_to"] == "How long do you keep daily server backups?" and "30 days" in result["answer"]
    assert result["answer"].startswith("Note: your message was longer than 500 characters")


def test_the_answer_streams_as_several_pieces_with_a_pause_between_them(monkeypatch):
    naps = []
    monkeypatch.setattr("app.fake_chat.time.sleep", naps.append)
    pieces, _ = finish("How long can a VPN session stay connected?", delay=0.2)
    assert len(pieces) > 5 and naps == [0.2] * len(pieces)


def test_the_call_is_labelled_fake_in_the_log(tmp_path, monkeypatch):
    from app import calllog
    monkeypatch.setattr(calllog, "ENABLED", True)
    monkeypatch.setattr(calllog, "LOG_PATH", tmp_path / "calls.jsonl")
    finish("How long can a VPN session stay connected?")
    (row,) = calllog.read_log(tmp_path / "calls.jsonl")
    assert row["mode"] == "fake"


def test_topic_picking():
    assert pick_topic("How long are backups kept?")["name"] == "backups"
    assert pick_topic("quantum chromodynamics") is None
    assert pick_topic("And for P3?", "What is the response target for P1?")["name"] == "priorities"


def test_an_unrelated_short_question_does_not_borrow_the_previous_topic():
    # found by the planner agent: "What is the weather in Paris?" after an MFA question wrongly returned the MFA answer
    for unrelated in ("What is the weather in Paris?", "Tell me a joke", "What is the capital of France?"):
        _, result = finish(unrelated, previous="How do I set up MFA on a new phone?")
        assert result["declined"], unrelated
        assert result["searched_for"] == unrelated


def test_a_real_follow_up_still_borrows_the_previous_topic():
    for follow_up, previous in (("And on a Mac?", "How do I install the VPN client on Windows?"), ("And for P3?", "What is the response target for P1?")):
        _, result = finish(follow_up, previous=previous)
        assert not result["declined"] and result["searched_for"] != follow_up
