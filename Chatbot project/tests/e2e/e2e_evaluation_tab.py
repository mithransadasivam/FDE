"""Browser test: open the Evaluation tab in a real browser and check the nine dimension cards and the verdict are shown."""
import re

from playwright.sync_api import Page, expect

from tests.e2e.helpers import TIMEOUT_MS, open_app, open_tab

DIMENSIONS = ["functional", "quality", "safety", "security", "robustness", "performance", "context", "ragas", "multimodal"]


def test_the_evaluation_tab_shows_nine_cards_and_a_verdict(page: Page, app_url: str):
    open_app(page, app_url)
    open_tab(page, "Evaluation")
    verdict = page.locator(".st-key-eval_verdict")
    expect(verdict).to_be_visible(timeout=TIMEOUT_MS)
    expect(verdict).to_contain_text("ship")  # "Ready to ship" or "Not ready to ship"
    for dimension in DIMENSIONS:
        card = page.locator(f".st-key-eval_card_{dimension}")
        expect(card).to_be_visible(timeout=TIMEOUT_MS)
        expect(card).to_contain_text(re.compile("PASS|FAIL|UNTESTED"))  # waits for the text to be drawn: every card shows a status
    expect(page.locator("[class*='st-key-eval_card_']")).to_have_count(9)


def test_each_card_has_a_number(page: Page, app_url: str):
    open_app(page, app_url)
    open_tab(page, "Evaluation")
    for dimension in DIMENSIONS:
        card = page.locator(f".st-key-eval_card_{dimension}")
        expect(card).to_contain_text(re.compile(r"\d|no data"), timeout=TIMEOUT_MS)
