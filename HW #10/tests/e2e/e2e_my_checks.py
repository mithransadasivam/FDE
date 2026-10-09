"""My browser checks: things the help desk's users rely on."""
from playwright.sync_api import Page, expect

from tests.e2e.e2e_chat_ui import TIMEOUT, ask


def test_an_error_code_question_cites_the_error_code_reference(page: Page, app_url: str):
    """A user who asks about an error code must see the error-code reference as a source."""
    ask(page, app_url, "What does error VPN-809 mean?")
    expect(page.get_by_text("Day07_Slide05_kb_error_codes.pdf").first).to_be_visible(timeout=TIMEOUT)
    expect(page.get_by_text("DECLINED")).to_have_count(0)
