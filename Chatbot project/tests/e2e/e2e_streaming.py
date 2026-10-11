"""Journey 16: the answer streams. The first words are on screen BEFORE the sources row, the badge and the timing line.

Runs against the fake chatbot, whose slow steady pieces make the moment between the first word and the end long enough to check
reliably (the real chatbot's answers are done in about two seconds). The streaming code path is the real one.
"""
import re

from playwright.sync_api import Page, expect

from tests.e2e.helpers import TIMEOUT_MS, answer_text, ask, open_app, wait_for_answer

QUESTION = "How long can a VPN session stay connected?"


def test_the_first_words_appear_before_the_sources_row_and_the_timing_line(page: Page, slow_fake_app_url: str):
    open_app(page, slow_fake_app_url)
    ask(page, QUESTION)
    live = page.locator(".st-key-stream_text")
    # the first words are on screen: some text, then the cursor that is shown while words are still arriving.
    # (The note "Searching the documents..." is also text, so a plain "is there a word" check would wait for the wrong thing.)
    expect(live).to_contain_text(re.compile(r"\w+\W*▌"), timeout=TIMEOUT_MS)
    # ...and nothing that belongs to a finished answer is there yet
    assert page.locator(".st-key-sources_1").count() == 0
    assert page.locator(".st-key-details_1").count() == 0
    assert page.locator(".st-key-badge_1").count() == 0


def test_the_finished_message_replaces_the_live_text_and_has_sources_timing_and_the_sidebar_times(page: Page, slow_fake_app_url: str):
    open_app(page, slow_fake_app_url)
    ask(page, QUESTION)
    wait_for_answer(page, 1)
    expect(page.locator(".st-key-stream_text")).to_have_count(0)  # the live version is gone
    expect(page.locator(".st-key-sources_1 .source-tag").first).to_be_visible(timeout=TIMEOUT_MS)
    expect(page.locator(".st-key-details_1")).to_contain_text("chunks")
    assert re.search(r"\[\d+\]", answer_text(page, 1))
    sidebar = page.locator('[data-testid="stSidebar"]')  # both times for the last question are in the sidebar
    expect(sidebar.get_by_text("First words after")).to_be_visible(timeout=TIMEOUT_MS)
    expect(sidebar.get_by_text("Full answer after")).to_be_visible()
