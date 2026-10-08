"""Helpers for browser tests of the chat page."""
from playwright.sync_api import Page

TIMEOUT = 90_000  # ms: an answer needs an embedding and a model call


def ask(page: Page, app_url: str, question: str) -> None:
    """Open the app, type a question in the chat box and press Enter."""
    page.goto(app_url)
    box = page.get_by_placeholder("Ask a question")
    box.wait_for(timeout=TIMEOUT)
    box.fill(question)
    box.press("Enter")
