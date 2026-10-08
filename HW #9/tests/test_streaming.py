"""Tells you when Activity 2 is done: all five tests pass. No model is used."""

from app.rag import DECLINE
from app.streaming import stream_answer
from tests.day09_fakes import FakeStreamClient

KEPT = [{"source": "vpn.pdf", "page": 1, "text": "A VPN session lasts 12 hours.", "score": 0.8}]


def test_no_chunks_means_the_decline_sentence_and_no_model_call():
    fake = FakeStreamClient("should not be used")
    assert list(stream_answer("What is for lunch?", [], client=fake)) == [DECLINE]
    assert fake.calls == []


def test_the_pieces_come_out_in_order():
    fake = FakeStreamClient("A VPN ", "session lasts ", "12 hours [1].")
    assert list(stream_answer("VPN?", KEPT, client=fake)) == ["A VPN ", "session lasts ", "12 hours [1]."]


def test_empty_and_missing_pieces_are_skipped():
    fake = FakeStreamClient("", "12 hours", None, " [1].")
    assert "".join(stream_answer("VPN?", KEPT, client=fake)) == "12 hours [1]."
    assert None not in list(stream_answer("VPN?", KEPT, client=FakeStreamClient(None, "ok")))


def test_the_model_is_asked_to_stream_at_temperature_0():
    fake = FakeStreamClient("ok")
    list(stream_answer("VPN?", KEPT, client=fake, model="m"))
    call = fake.calls[0]
    assert call["stream"] is True
    assert call["temperature"] == 0
    assert call["model"] == "m"


def test_the_prompt_holds_the_question_and_the_sources():
    fake = FakeStreamClient("ok")
    list(stream_answer("How long is a VPN session?", KEPT, client=fake))
    content = fake.calls[0]["messages"][0]["content"]
    assert "How long is a VPN session?" in content
    assert "A VPN session lasts 12 hours." in content
    assert len(fake.calls) == 1
