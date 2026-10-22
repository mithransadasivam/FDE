"""Day 17: security regression tests against the running chatbot, through its API and its chat page.

    GUARDRAILS=1 CHAT_FAKE=1 docker compose up -d --build chatbot     (then wait until it is healthy)
    pytest tests/e2e/e2e_security.py                                  (BASE_URL=http://localhost:8000)

Every direct attack from data/Day17_Slide09_attacks.json is sent to the service, and must be
stopped. Attacks with a planted document cannot be sent from outside: tests/test_security_regression.py
covers those. C03 is a known, accepted risk and is not tested here. Done: run it.
"""

import os

import httpx
import pytest
from playwright.sync_api import Page, expect

from app.guardrails import BLOCKED_MESSAGE
from app.red_team import load_attacks, score_attack
from tests.e2e.helpers import SOURCES, TIMEOUT, ask

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
ACCEPTED = {"C03"}
DIRECT = [
    a
    for a in load_attacks()
    if a["target"] == "chatbot" and not a.get("planted") and a["id"] not in ACCEPTED
]


@pytest.fixture(scope="module")
def service_url():
    try:
        settings = httpx.get(BASE_URL + "/metrics", timeout=3).json()["settings"]
    except httpx.HTTPError:
        pytest.skip(f"No chatbot service at {BASE_URL}: start the container first")
    if not settings.get("guardrails"):
        pytest.fail(
            "The service is running without guardrails: start it with GUARDRAILS=1"
        )
    return BASE_URL


@pytest.mark.parametrize("attack", DIRECT, ids=[a["id"] for a in DIRECT])
def test_each_direct_attack_is_stopped(service_url, attack):
    r = httpx.post(
        service_url + "/ask", json={"question": attack["prompt"]}, timeout=60
    )
    body = r.json()
    result = {
        "answer": body.get("answer", ""),
        "model": body.get("model"),
        "blocked": body.get("blocked", True),
        "calls": [],
        "notes": [],
    }
    assert score_attack(attack, result)["succeeded"] is False, body
    assert body["blocked"] is True and body["answer"] == BLOCKED_MESSAGE


def test_the_chat_page_shows_the_refusal(page: Page, service_url):
    ask(page, service_url, DIRECT[0]["prompt"])
    expect(page.get_by_text(BLOCKED_MESSAGE)).to_be_visible(timeout=TIMEOUT)


def test_an_ordinary_question_is_still_answered(page: Page, service_url):
    ask(page, service_url, "How long can a VPN session stay connected?")
    expect(page.get_by_text(SOURCES)).to_be_visible(timeout=TIMEOUT)
    expect(page.get_by_text(BLOCKED_MESSAGE)).to_have_count(0)
