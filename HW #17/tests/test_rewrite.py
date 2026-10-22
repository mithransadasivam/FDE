"""Tells you when Activity 4 is done: all five tests pass. The model is a fake."""

from app.rewrite import MAX_LENGTH, rewrite_query
from tests.day07_fakes import FakeChatClient


def test_returns_the_cleaned_rewrite():
    fake = FakeChatClient('  "P3 incident response target"\n')
    assert (
        rewrite_query("And what about P3?", client=fake)
        == "P3 incident response target"
    )


def test_the_previous_question_reaches_the_prompt():
    fake = FakeChatClient("P3 incident response target")
    rewrite_query(
        "And what about P3?",
        previous="What is the response target for a P1 incident?",
        client=fake,
    )
    prompt = fake.calls[0]["messages"][0]["content"]
    assert (
        "And what about P3?" in prompt and "response target for a P1 incident" in prompt
    )


def test_calls_the_model_once_at_temperature_zero():
    fake = FakeChatClient("VPN session time limit")
    rewrite_query("vpn kicks me out??", client=fake)
    assert len(fake.calls) == 1 and fake.calls[0]["temperature"] == 0


def test_an_empty_or_overlong_reply_falls_back_to_the_question():
    assert (
        rewrite_query("vpn kicks me out??", client=FakeChatClient("  "))
        == "vpn kicks me out??"
    )
    long_reply = "x" * (MAX_LENGTH + 1)
    assert (
        rewrite_query("vpn kicks me out??", client=FakeChatClient(long_reply))
        == "vpn kicks me out??"
    )


def test_a_reply_with_several_lines_falls_back_to_the_question():
    fake = FakeChatClient("Here is your query:\nVPN session time limit")
    assert rewrite_query("vpn kicks me out??", client=fake) == "vpn kicks me out??"
