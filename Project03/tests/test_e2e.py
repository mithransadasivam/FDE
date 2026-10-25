"""One end-to-end check of the running stack with Playwright. Skipped unless E2E_URL points at the Streamlit screen:

    docker compose up --build -d
    E2E_URL=http://localhost:8501 python -m pytest tests/test_e2e.py -m e2e
"""
import os
import re

import pytest

pytestmark = pytest.mark.e2e
URL = os.environ.get("E2E_URL")


@pytest.mark.skipif(not URL, reason="set E2E_URL to the running Streamlit screen")
def test_the_running_container_triages_asks_and_waits_for_approval():
    from playwright.sync_api import expect, sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1500, "height": 1000})
        page.goto(URL, wait_until="networkidle")
        expect(page.get_by_text("Operations Control Tower").first).to_be_visible(timeout=30000)
        page.get_by_role("button", name=re.compile("Triage the 22 starter alerts")).click()
        expect(page.get_by_text("INC-3003").first).to_be_visible(timeout=240000)
        expect(page.get_by_text("INC-3010").first).to_be_visible()  # the unknown service waits for a person
        expect(page.get_by_text("NEEDS PERSON").first).to_be_visible()
        # an incident waits for approval and nothing has run
        page.get_by_role("tab", name="Incident", exact=True).click()
        expect(page.get_by_text("Approvals").first).to_be_visible(timeout=30000)
        expect(page.get_by_text("Nothing has changed yet").first).to_be_visible()
        # a status question is answered with no model
        page.get_by_role("tab", name="Ask the tower", exact=True).click()
        page.get_by_placeholder("What is the status of the Payment Portal?").fill("What is the status of the Payment Portal?")
        page.keyboard.press("Enter")
        page.get_by_role("button", name="Ask").click()
        expect(page.get_by_text("route: data").first).to_be_visible(timeout=60000)
        browser.close()
