"""Day 16, Activity 4: choose_route() sends simple questions to the small model, the rest to the
large one, and says why."""

from fastapi.testclient import TestClient

from app.api import api
from app.router import choose_route

SURE = [{"score": 0.82}, {"score": 0.61}]


def test_a_short_plain_question_with_a_good_source_goes_small():
    assert choose_route("How long can a VPN session stay connected?", SURE) == {
        "route": "small",
        "reason": "simple question",
    }


def test_no_small_model_means_large():
    assert choose_route(
        "How long can a VPN session last?", SURE, small_available=False
    ) == {"route": "large", "reason": "no small model"}


def test_a_long_question_goes_large():
    q = "I am travelling for three weeks next month and my laptop may be off for a while so what happens to my VPN access"
    assert choose_route(q, SURE)["reason"] == "long question"


def test_several_questions_go_large():
    assert (
        choose_route("Is the VPN down? Can I use my phone?", SURE)["reason"]
        == "several questions"
    )


def test_a_reasoning_word_goes_large_and_is_named():
    assert choose_route("Why does my VPN disconnect after 12 hours?", SURE) == {
        "route": "large",
        "reason": "needs reasoning: why",
    }
    assert (
        choose_route("Compare the laptop and phone rules.", SURE)["reason"]
        == "needs reasoning: compare"
    )


def test_unsure_retrieval_goes_large():
    assert choose_route(
        "How long are logs kept?", [{"score": 0.55}, {"score": 0.52}]
    ) == {"route": "large", "reason": "unsure retrieval"}


def test_the_service_routes_and_falls_back_from_the_small_model(
    fake_chatbot, monkeypatch
):
    monkeypatch.setenv("ROUTING", "1")
    client = TestClient(api)
    simple = client.post(
        "/ask", json={"question": "How often are laptops replaced?"}
    ).json()
    hard = client.post(
        "/ask", json={"question": "Why are laptops replaced every 4 years?"}
    ).json()
    assert (simple["route"], simple["model"]) == ("small", "fake-small")
    assert (hard["route"], hard["model"]) == ("large", "fake-primary")
    monkeypatch.setenv("SIMULATE_OUTAGE", "small")
    down = client.post(
        "/ask", json={"question": "How often are laptops replaced?"}
    ).json()
    assert (down["route"], down["model"], down["fallback"]) == (
        "small",
        "fake-primary",
        True,
    )
