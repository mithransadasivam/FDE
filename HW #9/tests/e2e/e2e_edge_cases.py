"""Day 9 homework: edge-case browser tests for the streaming chat app.

Run them with:              pytest tests/e2e/e2e_edge_cases.py
Without models (as in CI):  CHAT_FAKE=1 pytest tests/e2e/e2e_edge_cases.py

Each test checks what must always be true (structure), never the exact wording of an answer.
Whenever a question is sent, the test waits for the "Sources:" or decline line, which the app
shows only when the answer is complete.
"""

from playwright.sync_api import Page, expect

from tests.e2e.helpers import CHAT_BOX, DECLINED, SOURCES, TIMEOUT, ask, messages

APP_FILE = "app/rag_app_stream.py"
FINISHED = (SOURCES, DECLINED)  # either line means the answer is complete


def wait_for_end_of_answer(page: Page, count: int = 1) -> None:
    """Wait until `count` answers have finished (each ends with a Sources or decline line)."""
    done = page.get_by_text(SOURCES).or_(page.get_by_text(DECLINED))
    expect(done).to_have_count(count, timeout=TIMEOUT)


# --- The three edge cases from the curriculum -------------------------------------------------

def test_an_empty_question_is_not_sent(page: Page, app_url: str):
    # An empty question, then a real one. If the empty one had been sent, there would be 4 messages.
    ask(page, app_url, "")
    ask(page, app_url, "How often are laptops replaced?", open_page=False)
    wait_for_end_of_answer(page)
    expect(messages(page)).to_have_count(2)  # only the real question and its answer
    expect(page.get_by_placeholder(CHAT_BOX)).to_be_enabled()


def test_a_very_long_question_gets_an_answer_or_a_decline_and_no_error(page: Page, app_url: str):
    pasted_log = "ERROR vpn-client connection reset by peer (retrying) " * 55  # about 3,000 characters
    assert 2_900 < len(pasted_log) < 3_100
    ask(page, app_url, pasted_log + " Why does my VPN keep disconnecting?")
    wait_for_end_of_answer(page)
    expect(page.get_by_test_id("stException")).to_have_count(0)
    expect(messages(page)).to_have_count(2)


def test_a_question_no_document_answers_is_declined_without_sources(page: Page, app_url: str):
    ask(page, app_url, "What is the capital city of Australia?")
    expect(page.get_by_text(DECLINED)).to_be_visible(timeout=TIMEOUT)
    expect(page.get_by_text(SOURCES)).to_have_count(0)


# --- My two edge cases ------------------------------------------------------------------------
# Why these two: users do paste odd characters (an emoji can break encoding or embedding code),
# and every real user reloads the page; stale or half-saved chat state is an easy bug to miss.

def test_a_single_emoji_gives_no_error(page: Page, app_url: str):
    ask(page, app_url, "\N{THUMBS UP SIGN}")
    wait_for_end_of_answer(page)  # a decline is fine
    expect(page.get_by_test_id("stException")).to_have_count(0)
    expect(page.get_by_placeholder(CHAT_BOX)).to_be_enabled()


def test_reloading_the_page_clears_the_chat(page: Page, app_url: str):
    ask(page, app_url, "How long can a VPN session stay connected?")
    wait_for_end_of_answer(page, 1)
    ask(page, app_url, "What is the password policy?", open_page=False)
    wait_for_end_of_answer(page, 2)
    expect(messages(page)).to_have_count(4)

    page.reload()
    expect(page.get_by_placeholder(CHAT_BOX)).to_be_visible(timeout=TIMEOUT)
    expect(messages(page)).to_have_count(0)
