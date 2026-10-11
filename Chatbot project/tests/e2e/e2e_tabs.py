"""Browser tests for the other tabs and the sidebar (journeys 10 to 13 and 15 in specs/BROWSER_TEST_PLAN.md).

Data tables are drawn on a canvas, so a test cannot read their cells. It reads the grid's row count instead (aria-rowcount counts the
header row too). Tests marked `real` need Ollama running for the embedding model; none of them calls the answer model.
"""
import re

import pytest
from playwright.sync_api import Page, expect

from app.config import DOCS_DIR, TOP_K
from app.retrieval import MODES
from tests.e2e.helpers import TIMEOUT_MS, no_error_on_page, open_app, open_tab


def grid_rows(page: Page, key: str) -> int:
    """How many data rows the table inside the container with this key has (header row not counted)."""
    grid = page.locator(f".st-key-{key} [role='grid']").first
    expect(grid).to_have_attribute("aria-rowcount", re.compile(r"\d+"), timeout=TIMEOUT_MS)
    return int(grid.get_attribute("aria-rowcount")) - 1


# --- 10. the knowledge base tab -----------------------------------------------------------------------------------------

@pytest.mark.index
def test_the_knowledge_base_lists_every_document_and_offers_rebuild_and_search(page: Page, app_url: str):
    open_app(page, app_url)
    open_tab(page, "Knowledge base")
    documents = len([p for p in DOCS_DIR.iterdir() if p.is_file()])
    expect(page.get_by_text(re.compile(rf"{documents} of {documents} documents indexed"))).to_be_visible(timeout=TIMEOUT_MS)
    assert grid_rows(page, "kb_table") == documents  # one row per document
    expect(page.get_by_role("button", name="↻ Rebuild index")).to_be_enabled()  # shown, never pressed by a test
    expect(page.get_by_label("Search the knowledge base")).to_be_visible()
    assert no_error_on_page(page)


# --- 11. the retrieval-only search ---------------------------------------------------------------------------------------

@pytest.mark.real
def test_the_retrieval_only_search_shows_scored_chunks_and_marks_those_below_the_minimum(page: Page, app_url: str):
    open_app(page, app_url)
    open_tab(page, "Knowledge base")
    box = page.get_by_label("Search the knowledge base")
    box.fill("How long do we keep server backups?")
    box.press("Enter")
    rows = page.get_by_text(re.compile(r"page \d+ · chunk \d+"))
    expect(rows.first).to_be_visible(timeout=30_000)
    assert rows.count() == TOP_K
    # a question the documents do not cover has scores below the minimum, and says so
    box.fill("What is the salary band for a senior engineer?")
    box.press("Enter")
    expect(page.get_by_text("below the minimum score").first).to_be_visible(timeout=30_000)
    assert no_error_on_page(page)


# --- 12. the test results tab -----------------------------------------------------------------------------------------

def test_the_test_results_tab_shows_the_summary_cards_and_a_row_per_question(page: Page, app_url: str):
    open_app(page, app_url)
    open_tab(page, "Test results")
    for card in ("Behaviour correct", "Answered when it should", "Declined when it should", "Average time per answer"):
        expect(page.get_by_test_id("stMetricLabel").filter(has_text=card).first).to_be_visible(timeout=TIMEOUT_MS)  # the card, not the sidebar
    assert grid_rows(page, "tests_table") == 10  # the 10 questions of the Part 1 test
    assert no_error_on_page(page)


# --- 13. the retrieval tab ---------------------------------------------------------------------------------------------

def test_the_retrieval_tab_compares_every_mode_and_has_the_side_by_side_view(page: Page, app_url: str):
    open_app(page, app_url)
    open_tab(page, "Retrieval")
    expect(page.get_by_text(re.compile(r"Hit rate @4 \(smart\)")).first).to_be_visible(timeout=TIMEOUT_MS)
    assert grid_rows(page, "retrieval_table") == len(MODES)  # one row per mode
    expect(page.get_by_role("heading", name=re.compile("What was found"))).to_be_visible()
    expect(page.get_by_text("Mode A")).to_be_visible()
    expect(page.get_by_text("Mode B")).to_be_visible()
    assert no_error_on_page(page)


# --- 15. the sidebar -------------------------------------------------------------------------------------------------

@pytest.mark.index
def test_the_sidebar_shows_status_settings_mode_and_gate(page: Page, app_url: str):
    open_app(page, app_url)
    sidebar = page.locator('[data-testid="stSidebar"]')
    expect(page.locator(".st-key-sidebar_kb_status")).to_contain_text("READY", timeout=TIMEOUT_MS)
    expect(page.locator(".st-key-sidebar_kb_status")).to_contain_text("documents")
    expect(sidebar.get_by_text("Chunk size")).to_be_visible()
    expect(page.locator(".st-key-sidebar_mode_chips .chip-on")).to_have_text("smart")
    expect(sidebar.get_by_text("Dimensions passing")).to_be_visible()
    expect(sidebar.get_by_text("Clear chat")).to_be_visible()
