"""Day 9, Activity 1: end-to-end tests of the Day 6 chat app, in a real browser, with Playwright.

Run them with:  pytest tests/e2e/e2e_chat_ui.py
The file name does not start with test_, so the quick unit-test run (pytest -q) skips these
slower tests, which start the app and call the real models.
Two tests are done. Activity 1: fill in the third.
"""

from playwright.sync_api import Page, expect

from tests.e2e.helpers import DECLINED, SOURCES, TIMEOUT, ask  # noqa: F401  (you will need it)

# Tells conftest.py which app to start for this file (see the app_url fixture).
APP_FILE = "app/rag_app.py"


def test_the_page_opens_with_its_title(page: Page, app_url: str):
    # `page` is a fresh Chromium tab from pytest-playwright; `app_url` is the running app's address.
    page.goto(app_url)
    # Streamlit draws the page with JavaScript, so expect() waits (up to TIMEOUT) for the heading.
    expect(page.get_by_role("heading", name="Ask the IT policies")).to_be_visible(timeout=TIMEOUT)


def test_an_answerable_question_shows_its_sources(page: Page, app_url: str):
    # Type the question in the chat box and press Enter (helper from tests/e2e/helpers.py).
    ask(page, app_url, "How long can a VPN session stay connected?")
    # The "Sources: ..." caption appears only when the bot answered from the documents.
    expect(page.get_by_text(SOURCES)).to_be_visible(timeout=TIMEOUT)


def test_a_question_the_documents_dont_cover_shows_no_sources(page: Page, app_url: str):
    """A question the policies don't cover must be declined, with no sources."""
    # An off-topic question: the policies say nothing about the cafeteria.
    ask(page, app_url, "What is on the cafeteria menu this week?")
    # The page must show the "No sources: the bot declined." caption...
    expect(page.get_by_text(DECLINED)).to_be_visible(timeout=TIMEOUT)
    # ...and no "Sources: " line at all (zero matching elements).
    expect(page.get_by_text(SOURCES)).to_have_count(0)
