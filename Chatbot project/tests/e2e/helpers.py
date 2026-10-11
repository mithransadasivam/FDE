"""Shared steps for the browser tests: open a tab, ask a question, wait for the answer to finish, read what is on screen.

Everything is found by role, visible text, placeholder or a key the app puts on its elements (`st-key-...`).
Nothing waits a fixed number of seconds: every wait is for something that only appears when the work is done.
"""
import os

from playwright.sync_api import Page, expect

TABS = ["Chat", "Knowledge base", "Test results", "Retrieval", "Evaluation"]
TAB_HEADINGS = {
    "Chat": "💬 Ask the help desk", "Knowledge base": "📚 Knowledge base", "Test results": "🧪 Test results",
    "Retrieval": "🔎 Retrieval", "Evaluation": "📊 Evaluation",
}
CHAT_PLACEHOLDER = "Ask a question about your IT documents…"

# How long a wait may last before the test gives up. Long enough for a slow real model, short enough that a real failure
# does not take minutes. Both can be shortened from outside (E2E_TIMEOUT_MS, E2E_ANSWER_TIMEOUT_MS) when a failure is expected.
TIMEOUT_MS = int(os.getenv("E2E_TIMEOUT_MS", "15000"))               # something already on the page, or a quick fake answer
ANSWER_TIMEOUT_MS = int(os.getenv("E2E_ANSWER_TIMEOUT_MS", "90000"))  # the real chatbot: search, then the answer model


def open_app(page: Page, app_url: str) -> None:
    page.goto(app_url)
    expect(page.get_by_role("heading", name="🛠 IT Help Desk Assistant").first).to_be_visible(timeout=TIMEOUT_MS)


def open_tab(page: Page, name: str) -> None:
    page.get_by_role("tab", name=name).click()
    expect(page.get_by_role("heading", name=TAB_HEADINGS[name], exact=True)).to_be_visible(timeout=TIMEOUT_MS)


def chat_box(page: Page):
    return page.get_by_placeholder(CHAT_PLACEHOLDER)


def ask(page: Page, question: str) -> None:
    """Type a question into the chat box and send it."""
    box = chat_box(page)
    box.fill(question)
    box.press("Enter")


def paste(page: Page, text: str) -> None:
    """Put a long text into the chat box in one go (typing 3,000 characters key by key would be slow) and send it."""
    box = chat_box(page)
    box.fill(text)
    box.press("Enter")


def messages(page: Page):
    """The chat messages on the page (user and assistant). Use `expect(messages(page)).to_have_count(n)`: it waits for the page to settle."""
    return page.locator('[class*="st-key-user_message_"], [class*="st-key-assistant_message_"]')


def message_count(page: Page) -> int:
    """How many chat messages are on the page right now (no waiting: prefer `expect(messages(page)).to_have_count(n)`)."""
    return messages(page).count()


def assistant(page: Page, index: int):
    """The container of the assistant message with this index (the index counts every message, user ones too)."""
    return page.locator(f".st-key-assistant_message_{index}")


def wait_for_answer(page: Page, index: int, timeout: int = ANSWER_TIMEOUT_MS):
    """Wait until the answer at `index` is finished: its timing line is the last thing drawn. Returns the container."""
    message = assistant(page, index)
    expect(page.locator(f".st-key-details_{index}")).to_be_visible(timeout=timeout)
    return message


def answer_text(page: Page, index: int) -> str:
    return page.locator(f".st-key-answer_{index}").inner_text()


def source_tags(page: Page, index: int):
    return page.locator(f".st-key-sources_{index} .source-tag")


def badge_text(page: Page, index: int) -> str:
    """'DECLINED', 'REFUSED' or '' when the answer has no badge."""
    badge = page.locator(f".st-key-badge_{index}")
    return badge.inner_text().strip() if badge.count() else ""


def no_error_on_page(page: Page) -> bool:
    """True when no Python error box (an exception with a traceback) is shown."""
    return page.locator('[data-testid="stException"]').count() == 0
