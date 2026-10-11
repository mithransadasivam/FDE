"""Journey 26: thumbs up and down under an answer. Against the fake chatbot; the rating code and the screens are the real ones.

The fake app runs with CALL_LOG=0, which also switches the feedback log off, so these journeys never write to the real log.
"""
from playwright.sync_api import Page, expect

from tests.e2e.helpers import TIMEOUT_MS, ask, open_app, open_tab, wait_for_answer

QUESTION = "How long can a VPN session stay connected?"


def test_a_thumbs_up_is_thanked_and_the_buttons_go_away(page: Page, fake_app_url: str):
    open_app(page, fake_app_url)
    ask(page, QUESTION)
    wait_for_answer(page, 1)
    expect(page.locator(".st-key-fb_up_1")).to_be_visible(timeout=TIMEOUT_MS)
    page.locator(".st-key-fb_up_1 button").first.click()
    expect(page.locator(".st-key-feedback_1").filter(has_text="Thanks for the feedback")).to_have_count(1, timeout=TIMEOUT_MS)
    expect(page.locator(".st-key-fb_up_1")).to_have_count(0, timeout=TIMEOUT_MS)  # one rating per answer
    expect(page.locator(".st-key-fb_down_1")).to_have_count(0)


def test_a_thumbs_down_asks_for_a_reason_and_keeps_the_question_private_unless_the_box_is_ticked(page: Page, fake_app_url: str):
    open_app(page, fake_app_url)
    ask(page, QUESTION)
    wait_for_answer(page, 1)
    page.locator(".st-key-fb_down_1 button").first.click()
    box = page.get_by_label("Also save my question, to help fix it (leave unticked to keep it private)")
    expect(box).to_be_visible(timeout=TIMEOUT_MS)
    expect(box).not_to_be_checked()  # private by default
    expect(page.get_by_text("What was wrong?")).to_be_visible()
    page.locator(".st-key-fb_send_1 button").first.click()
    expect(page.locator(".st-key-feedback_1").filter(has_text="Thanks")).to_have_count(1, timeout=TIMEOUT_MS)


def test_each_answer_has_its_own_buttons_and_a_declined_answer_can_be_rated_too(page: Page, fake_app_url: str):
    open_app(page, fake_app_url)
    ask(page, QUESTION)
    wait_for_answer(page, 1)
    ask(page, "What is the salary band for a senior engineer?")
    wait_for_answer(page, 3)
    expect(page.locator(".st-key-fb_up_1")).to_be_visible(timeout=TIMEOUT_MS)
    expect(page.locator(".st-key-fb_up_3")).to_be_visible()
    page.locator(".st-key-fb_down_3 button").first.click()
    page.locator(".st-key-fb_send_3 button").first.click()
    expect(page.locator(".st-key-feedback_3").filter(has_text="Thanks")).to_have_count(1, timeout=TIMEOUT_MS)
    expect(page.locator(".st-key-fb_up_1")).to_be_visible()  # the first answer is still unrated


def test_the_evaluation_tab_has_the_feedback_review_section(page: Page, fake_app_url: str):
    open_app(page, fake_app_url)
    open_tab(page, "Evaluation")
    expect(page.get_by_role("heading", name="What people said about the answers")).to_be_visible(timeout=TIMEOUT_MS)
    expect(page.locator(".st-key-feedback_review")).to_be_visible()
