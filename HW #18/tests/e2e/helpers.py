"""Shared helpers for the browser tests. Done: you don't need to change them."""

import re

from playwright.sync_api import Page

TIMEOUT = 30_000  # milliseconds: a real answer can take several seconds
SOURCES = re.compile(r"^Sources: ")
DECLINED = "No sources: the bot declined."
CHAT_BOX = "Ask a question about the IT policies"


def ask(page: Page, app_url: str, question: str, open_page: bool = True) -> None:
    """Open the app (unless it is already open), type a question in the chat box and press Enter."""
    if open_page:
        page.goto(app_url)
    box = page.get_by_placeholder(CHAT_BOX)
    box.fill(question)
    box.press("Enter")


def messages(page: Page):
    """All chat messages on the page, user and assistant, in order."""
    return page.get_by_test_id("stChatMessage")


def last_answer_text(page: Page) -> str:
    """The text of the last answer, without its Sources line."""
    return messages(page).last.get_by_test_id("stMarkdownContainer").first.inner_text().strip()
