"""Day 9, Activity 2: browser tests for the streaming chat app. Done: run them after Activity 2.

Run them with:              pytest tests/e2e/e2e_streaming.py
Without models (as in CI):  CHAT_FAKE=1 pytest tests/e2e/e2e_streaming.py

The answer arrives piece by piece. Checking too early sees half an answer, so every test first
waits for the "Sources:" or decline line, which the app shows only when the answer is complete.
"""

import re

from playwright.sync_api import Page, expect

from tests.e2e.helpers import DECLINED, SOURCES, TIMEOUT, ask, last_answer_text, messages

APP_FILE = "app/rag_app_stream.py"
CITATION = re.compile(r"\[\d+\]")


def test_a_streamed_answer_ends_with_a_citation_and_its_sources(page: Page, app_url: str):
    ask(page, app_url, "How long can a VPN session stay connected?")
    expect(page.get_by_text(SOURCES)).to_be_visible(timeout=TIMEOUT)  # the stream has finished
    assert CITATION.search(last_answer_text(page)), "the answer has no [n] citation"


def test_a_streamed_decline_shows_no_sources(page: Page, app_url: str):
    ask(page, app_url, "What is on the cafeteria menu this week?")
    expect(page.get_by_text(DECLINED)).to_be_visible(timeout=TIMEOUT)
    expect(page.get_by_text(SOURCES)).to_have_count(0)


def test_two_questions_in_a_row_give_four_messages(page: Page, app_url: str):
    ask(page, app_url, "How long can a VPN session stay connected?")
    expect(page.get_by_text(SOURCES)).to_be_visible(timeout=TIMEOUT)
    ask(page, app_url, "How often are laptops replaced?", open_page=False)
    expect(messages(page)).to_have_count(4, timeout=TIMEOUT)
    expect(page.get_by_text(SOURCES)).to_have_count(2, timeout=TIMEOUT)
