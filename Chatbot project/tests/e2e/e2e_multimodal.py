"""Journeys 20 to 25: pictures, tickets, voice notes, scanned documents and pictures out, against the fake chatbot.

The fake replaces only the models (reading a picture, listening, drawing, embedding). Every check, limit and screen is the real code, so
these run in the quick CI job without any key. The test files are the ones in data/multimodal.
"""
import re
from pathlib import Path

from playwright.sync_api import Page, expect

from tests.e2e.helpers import TIMEOUT_MS, answer_text, ask, badge_text, open_app, open_tab, source_tags, wait_for_answer

MEDIA = Path(__file__).resolve().parent.parent.parent / "data" / "multimodal"
CHAT_FILE_INPUT = '[data-testid="stChatInput"] input[type="file"]'


def attach_and_send(page: Page, screenshot: str, question: str = "") -> None:
    page.locator(CHAT_FILE_INPUT).first.set_input_files(str(MEDIA / "screenshots" / screenshot))
    expect(page.locator('[data-testid="stChatInput"]')).to_contain_text(screenshot, timeout=TIMEOUT_MS)
    if question:
        page.get_by_placeholder("Ask a question about your IT documents…").fill(question)
    page.locator('[data-testid="stChatInputSubmitButton"]').click()


def test_a_screenshot_gets_a_cited_answer_and_says_what_was_read_from_it(page: Page, multimodal_app_url: str):
    open_app(page, multimodal_app_url)
    attach_and_send(page, "vpn_809.png")
    wait_for_answer(page, 1)
    assert badge_text(page, 1) == ""
    expect(source_tags(page, 1).first).to_contain_text("Day07_Slide05_kb_error_codes.pdf", timeout=TIMEOUT_MS)
    expect(page.locator(".st-key-details_1")).to_contain_text("Read from the picture: VPN-809")
    expect(page.locator(".st-key-user_message_0 img")).to_be_visible()  # the small preview stays in the chat
    assert re.search(r"\[\d+\]", answer_text(page, 1))


def test_a_picture_that_is_not_an_it_problem_is_declined_with_no_sources(page: Page, multimodal_app_url: str):
    open_app(page, multimodal_app_url)
    attach_and_send(page, "hard_not_it.png")
    wait_for_answer(page, 1)
    assert badge_text(page, 1) == "DECLINED"
    assert source_tags(page, 1).count() == 0


def test_creating_a_ticket_from_a_screenshot_fills_every_field_and_can_be_downloaded(page: Page, multimodal_app_url: str):
    open_app(page, multimodal_app_url)
    attach_and_send(page, "vpn_809.png")
    wait_for_answer(page, 1)
    page.get_by_role("button", name="🎫 Create ticket from this screenshot").click()
    card = page.locator(".st-key-ticket_1")
    expect(card).to_be_visible(timeout=TIMEOUT_MS)
    expect(card).to_contain_text("VPN-809")
    expect(card).to_contain_text("NorthLink")
    for label in ("Summary", "Next step"):
        expect(card.get_by_label(label)).not_to_have_value("")
    expect(card.get_by_label("Severity")).to_be_visible()
    expect(card).to_contain_text("Next step from Day07_Slide05_kb_error_codes.pdf")
    with page.expect_download() as download:
        page.locator(".st-key-download_csv_1 button").click()
    assert download.value.suggested_filename == "ticket_VPN-809.csv"
    expect(page.locator('[data-testid="stSidebar"]')).to_contain_text("VPN-809")  # the session list of tickets


def test_a_voice_note_is_written_down_in_a_box_that_can_be_corrected_then_asked_like_a_typed_question(page: Page, multimodal_app_url: str):
    open_app(page, multimodal_app_url)
    page.get_by_text("🎤 Ask by voice").click()
    page.locator(".st-key-voice_upload input[type='file']").set_input_files(str(MEDIA / "voice" / "voice_session.wav"))
    page.get_by_role("button", name="Write it down").click()
    box = page.get_by_label("What I heard (fix it if it is wrong)")
    expect(box).to_have_value(re.compile("session stay connected"), timeout=TIMEOUT_MS)
    box.fill("How long can a VPN session stay connected?")  # the person fixes the words
    box.press("Control+Enter")
    page.get_by_role("button", name="Ask this question").click()
    wait_for_answer(page, 1)
    expect(page.locator(".st-key-user_message_0")).to_contain_text("How long can a VPN session stay connected?")
    expect(source_tags(page, 1).first).to_be_visible(timeout=TIMEOUT_MS)


def test_a_silent_voice_note_asks_to_try_again_and_sends_nothing(page: Page, multimodal_app_url: str):
    open_app(page, multimodal_app_url)
    page.get_by_text("🎤 Ask by voice").click()
    page.locator(".st-key-voice_upload input[type='file']").set_input_files(str(MEDIA / "voice" / "voice_silent.wav"))
    page.get_by_role("button", name="Write it down").click()
    expect(page.get_by_text("I could not hear a question in that recording")).to_be_visible(timeout=TIMEOUT_MS)
    assert page.get_by_label("What I heard (fix it if it is wrong)").count() == 0
    assert page.locator('[class*="st-key-user_message_"]').count() == 0


def test_a_scanned_document_can_be_added_read_and_indexed_with_the_cost_shown_first(page: Page, multimodal_app_url: str):
    open_app(page, multimodal_app_url)
    open_tab(page, "Knowledge base")
    page.get_by_text("➕ Add a document").click()
    page.locator('[class*="st-key-kb_upload"] input[type="file"]').set_input_files(str(MEDIA / "scans" / "visitor_notice_scanned.pdf"))
    expect(page.get_by_text(re.compile(r"1 of them scanned\. Reading them takes 1 vision calls"))).to_be_visible(timeout=TIMEOUT_MS)
    page.get_by_role("button", name="Add to the knowledge base").click()
    expect(page.get_by_text(re.compile(r"visitor_notice_scanned\.pdf added and 1 page read"))).to_be_visible(timeout=TIMEOUT_MS)
    table = page.locator(".st-key-kb_table")
    expect(table).to_be_visible()
    page.get_by_role("button", name="↻ Rebuild index").click()
    expect(page.get_by_text(re.compile(r"Index rebuilt: \d+ chunks"))).to_be_visible(timeout=TIMEOUT_MS)


def test_the_picture_button_draws_a_labelled_picture_only_when_pressed(page: Page, multimodal_app_url: str):
    open_app(page, multimodal_app_url)
    ask(page, "How long can a VPN session stay connected?")
    wait_for_answer(page, 1)
    assert page.locator(".st-key-illustration_1").count() == 0  # nothing is drawn until the button is pressed
    page.get_by_role("button", name=re.compile("Draw a picture for this answer")).click()
    picture = page.locator(".st-key-illustration_1")
    expect(picture).to_be_visible(timeout=TIMEOUT_MS)
    expect(picture.locator("img")).to_be_visible()
    expect(picture).to_contain_text("AI-generated illustration")


def test_the_picture_button_is_absent_when_pictures_are_off(page: Page, fake_app_url: str):
    open_app(page, fake_app_url)
    ask(page, "How long can a VPN session stay connected?")
    wait_for_answer(page, 1)
    assert page.get_by_role("button", name=re.compile("Draw a picture")).count() == 0
