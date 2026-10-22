"""Day 15: check the deployed chatbot from the outside, the way users and the CI pipeline see it.
Done: run it while the container is up.

    docker compose up -d --build          (then wait until it is healthy)
    pytest tests/e2e/e2e_container.py     (BASE_URL=http://localhost:8000 by default)

The browser tests reuse Day 9's helpers: the chat page has the same box, Sources line and decline
line as the Streamlit app. The answers asserted here are the fake chatbot's (CHAT_FAKE=1 in CI).
"""

import os
import re

import httpx
import pytest
from playwright.sync_api import Page, expect

from tests.e2e.helpers import DECLINED, SOURCES, TIMEOUT, ask

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
CITATION = re.compile(r"\[\d+\]")


@pytest.fixture(scope="module")
def service_url():
    try:
        httpx.get(BASE_URL + "/health", timeout=3)
    except httpx.HTTPError:
        pytest.skip(f"No chatbot service at {BASE_URL}: start the container first")
    return BASE_URL


def test_the_service_is_alive_and_ready(service_url):
    assert httpx.get(service_url + "/health").json() == {"status": "ok"}
    ready = httpx.get(service_url + "/ready").json()
    assert ready["ready"] is True, ready["checks"]


def test_the_api_answers_with_sources(service_url):
    body = httpx.post(
        service_url + "/ask",
        json={"question": "How long can a VPN session stay connected?"},
        timeout=60,
    ).json()
    assert (
        CITATION.search(body["answer"])
        and body["sources"]
        and body["declined"] is False
    )


def test_the_api_refuses_an_empty_question(service_url):
    assert httpx.post(service_url + "/ask", json={"question": ""}).status_code == 422


def test_the_chat_page_streams_an_answer_with_its_sources(page: Page, service_url):
    ask(page, service_url, "How long can a VPN session stay connected?")
    expect(page.get_by_text(SOURCES)).to_be_visible(timeout=TIMEOUT)


def test_the_chat_page_declines_an_off_topic_question(page: Page, service_url):
    ask(page, service_url, "What is on the cafeteria menu this week?")
    expect(page.get_by_text(DECLINED)).to_be_visible(timeout=TIMEOUT)


def test_the_dashboard_counts_the_requests(page: Page, service_url):
    page.goto(service_url + "/dashboard")
    expect(page.get_by_text("Chatbot dashboard")).to_be_visible()
    assert httpx.get(service_url + "/metrics").json()["requests"] >= 2
