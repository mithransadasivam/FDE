"""Smoke test: the app opens, and every tab opens with its heading visible and no error box. No chatbot is used."""
import pytest
from playwright.sync_api import Page, expect

from tests.e2e.helpers import TIMEOUT_MS, TABS, no_error_on_page, open_app, open_tab


def test_the_app_opens_with_all_five_tabs(page: Page, app_url: str):
    open_app(page, app_url)
    for name in TABS:
        expect(page.get_by_role("tab", name=name)).to_be_visible(timeout=TIMEOUT_MS)
    assert page.get_by_role("tab").count() == len(TABS)
    assert no_error_on_page(page)


@pytest.mark.parametrize("tab", TABS)
def test_each_tab_opens_with_its_heading_and_no_error_box(page: Page, app_url: str, tab: str):
    open_app(page, app_url)
    open_tab(page, tab)
    assert no_error_on_page(page), tab


@pytest.mark.index
def test_the_sidebar_shows_the_knowledge_base_status_and_the_chosen_mode(page: Page, app_url: str):
    open_app(page, app_url)
    status = page.locator(".st-key-sidebar_kb_status")
    expect(status).to_contain_text("READY", timeout=TIMEOUT_MS)
    expect(page.locator(".st-key-sidebar_mode_chips .chip-on")).to_have_text("smart")


def test_the_fake_chatbot_banner_is_never_shown_on_the_real_app(page: Page, app_url: str):
    open_app(page, app_url)
    assert page.locator(".st-key-fake_banner").count() == 0
    assert "FAKE CHATBOT" not in page.locator("body").inner_text()


def test_the_fake_chatbot_banner_is_shown_on_the_fake_app(page: Page, fake_app_url: str):
    open_app(page, fake_app_url)
    expect(page.locator(".st-key-fake_banner")).to_contain_text("FAKE CHATBOT", timeout=TIMEOUT_MS)
