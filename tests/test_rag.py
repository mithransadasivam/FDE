"""Tells you when Activity 3 is done: all five tests pass. No real model or database is used."""

from app.rag import DECLINE, answer
from tests.day06_fakes import FakeChatClient, fake_retriever

VPN = {
    "text": "A VPN session stays connected for a maximum of 12 hours.",
    "source": "policy_vpn.pdf",
    "page": 1,
    "score": 0.78,
}
WEAK = {
    "text": "Laptops are replaced every 4 years.",
    "source": "policy_equipment.pdf",
    "page": 1,
    "score": 0.31,
}


def test_declines_without_calling_the_model_when_nothing_is_relevant():
    fake = FakeChatClient("should not be used")
    result = answer(
        "What is on the cafeteria menu?",
        retrieve=fake_retriever(WEAK),
        client=fake,
        min_score=0.5,
    )
    assert result == {"answer": DECLINE, "sources": [], "declined": True}
    assert fake.calls == []


def test_answers_from_relevant_chunks_with_sources():
    fake = FakeChatClient("A VPN session can stay connected for 12 hours [1].")
    result = answer(
        "How long can a VPN session last?",
        retrieve=fake_retriever(VPN, WEAK),
        client=fake,
        min_score=0.5,
    )
    assert result["declined"] is False
    assert result["sources"] == ["policy_vpn.pdf, page 1"]
    assert "12 hours" in result["answer"]


def test_only_relevant_chunks_reach_the_prompt():
    fake = FakeChatClient("12 hours [1].")
    answer(
        "How long can a VPN session last?",
        retrieve=fake_retriever(VPN, WEAK),
        client=fake,
        min_score=0.5,
    )
    prompt = fake.calls[0]["messages"][0]["content"]
    assert (
        "maximum of 12 hours" in prompt and "How long can a VPN session last?" in prompt
    )
    assert "replaced every 4 years" not in prompt


def test_calls_the_model_once_at_temperature_zero():
    fake = FakeChatClient("12 hours [1].")
    answer(
        "How long can a VPN session last?",
        retrieve=fake_retriever(VPN),
        client=fake,
        min_score=0.5,
    )
    assert len(fake.calls) == 1 and fake.calls[0]["temperature"] == 0


def test_model_declining_is_reported_as_declined():
    fake = FakeChatClient(DECLINE)
    result = answer(
        "Who approves VPN for contractors?",
        retrieve=fake_retriever(VPN),
        client=fake,
        min_score=0.5,
    )
    assert result["declined"] is True
