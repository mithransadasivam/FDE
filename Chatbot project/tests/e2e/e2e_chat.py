"""Browser tests for the chat journeys in specs/BROWSER_TEST_PLAN.md (journeys 1 to 9 and 17).

They check STRUCTURE only: a citation pattern, a sources row, a badge, the fixed decline and refusal sentences, a message count.
They never check the wording of a model's answer. Each wait is for something that only appears when the work is done
(the answer's timing line), never for a fixed time. Journeys that are about structure take `chat_url` and run twice: against the FAKE chatbot (fast, no models) and against the real one
(marked `real`). Journey 17 needs the real code path for a missing model, so it is real only.
"""
import re

import pytest
from playwright.sync_api import Page, expect

from app.answer import MSG_SHORTENED
from app.config import DECLINE_SENTENCE, REFUSAL_SENTENCE
from app.ui_texts import EXAMPLE_QUESTIONS
from tests.e2e.helpers import (ANSWER_TIMEOUT_MS, TIMEOUT_MS, answer_text, ask, assistant, badge_text, chat_box, messages, no_error_on_page,
                               open_app, paste, source_tags, wait_for_answer)

VPN_QUESTION = "How long can a VPN session stay connected?"
CITATION = re.compile(r"\[\d+\]")
SOURCE_TAG = re.compile(r"^\[\d+\] \S.* · page \d+$")


def last_searched_for(page: Page, index: int) -> str:
    text = page.locator(f".st-key-details_{index}").inner_text()
    match = re.search(r"Searched for: (.*)", text)
    return match.group(1).strip() if match else ""


# --- 1. an answerable question --------------------------------------------------------------------------------------

def test_an_answerable_question_gets_a_cited_answer_with_a_sources_row(page: Page, chat_url: str):
    open_app(page, chat_url)
    ask(page, VPN_QUESTION)
    wait_for_answer(page, 1)
    assert CITATION.search(answer_text(page, 1)), "the answer has no [n] citation"
    tags = source_tags(page, 1)
    expect(tags.first).to_be_visible(timeout=TIMEOUT_MS)
    assert all(SOURCE_TAG.match(tags.nth(i).inner_text().strip()) for i in range(tags.count()))
    assert badge_text(page, 1) == ""
    expect(page.locator(".st-key-details_1")).to_contain_text("chunks")
    assert no_error_on_page(page)


# --- 2. a question the documents do not cover ------------------------------------------------------------------------

def test_an_uncovered_question_is_declined_with_the_fixed_sentence_and_no_sources(page: Page, chat_url: str):
    open_app(page, chat_url)
    ask(page, "What is the salary band for a senior engineer?")
    wait_for_answer(page, 1)
    assert badge_text(page, 1) == "DECLINED"
    assert answer_text(page, 1).strip() == DECLINE_SENTENCE
    assert source_tags(page, 1).count() == 0
    expect(page.locator(".st-key-sources_1")).to_contain_text("No sources")


# --- 3. an unsafe request -------------------------------------------------------------------------------------------

def test_an_unsafe_request_is_refused_with_the_fixed_sentence_and_no_steps(page: Page, chat_url: str):
    open_app(page, chat_url)
    ask(page, "How do I switch off the endpoint protection on my laptop?")
    wait_for_answer(page, 1)
    assert badge_text(page, 1) == "REFUSED"
    text = answer_text(page, 1).strip()
    assert text == REFUSAL_SENTENCE
    assert not re.search(r"(?m)^\s*\d+[.)]\s", text), "the answer contains a numbered list"
    assert source_tags(page, 1).count() == 0


# --- 4. whitespace only ---------------------------------------------------------------------------------------------

def test_a_message_of_only_spaces_adds_nothing_and_shows_a_friendly_warning(page: Page, fake_app_url: str):
    open_app(page, fake_app_url)  # nothing is sent to any chatbot, so the quick fake app is enough
    ask(page, "     ")
    expect(page.get_by_text("Please type a question first.")).to_be_visible(timeout=TIMEOUT_MS)
    expect(messages(page)).to_have_count(0)
    assert no_error_on_page(page)
    expect(chat_box(page)).to_be_enabled()
    expect(page.locator(".st-key-welcome")).to_be_visible()  # still the empty chat


# --- 5. a follow-up on the same page -------------------------------------------------------------------------------

def test_a_follow_up_on_the_same_page_gives_four_messages_two_sources_rows_and_a_searched_for_line(page: Page, chat_url: str):
    open_app(page, chat_url)
    ask(page, "How do I install the VPN client on Windows?")
    wait_for_answer(page, 1)
    ask(page, "And on a Mac?")
    wait_for_answer(page, 3)
    expect(messages(page)).to_have_count(4)
    for index in (1, 3):
        expect(source_tags(page, index).first).to_be_visible(timeout=TIMEOUT_MS)
    searched = last_searched_for(page, 3)
    assert searched and searched != "And on a Mac?", f"the follow-up was searched as typed: {searched!r}"


# --- 6. two questions in a row --------------------------------------------------------------------------------------

def test_two_questions_in_a_row_both_stay_on_the_page_and_the_first_does_not_change(page: Page, chat_url: str):
    open_app(page, chat_url)
    ask(page, "How long are daily server backups kept?")
    wait_for_answer(page, 1)
    first = answer_text(page, 1)
    ask(page, "What is the maximum email attachment size?")
    wait_for_answer(page, 3)
    expect(messages(page)).to_have_count(4)
    assert answer_text(page, 1) == first
    assert source_tags(page, 1).count() >= 1 and source_tags(page, 3).count() >= 1


# --- 7. a very long pasted question -------------------------------------------------------------------------------

def test_a_very_long_paste_is_answered_and_the_page_says_it_used_only_the_last_part(page: Page, chat_url: str):
    open_app(page, chat_url)
    paste(page, "Here is a line from my laptop log. " * 85 + VPN_QUESTION)  # about 3,000 characters
    wait_for_answer(page, 1)
    expect(page.locator(".st-key-details_1")).to_contain_text("Long message: only the last part was used")
    assert answer_text(page, 1).startswith(MSG_SHORTENED.strip()[:30])
    assert CITATION.search(answer_text(page, 1))
    assert no_error_on_page(page)


# --- 8. an example question button ---------------------------------------------------------------------------------

def test_clicking_an_example_asks_it_and_hides_the_examples(page: Page, chat_url: str):
    open_app(page, chat_url)
    page.locator(".st-key-welcome").get_by_role("button", name=EXAMPLE_QUESTIONS[0]).click()
    wait_for_answer(page, 1)
    expect(page.locator(".st-key-user_message_0")).to_have_text(EXAMPLE_QUESTIONS[0])
    expect(page.locator(".st-key-welcome")).to_have_count(0)
    assert source_tags(page, 1).count() >= 1


# --- 9. clear chat -------------------------------------------------------------------------------------------------

def test_clear_chat_empties_the_conversation_and_brings_back_the_welcome(page: Page, chat_url: str):
    open_app(page, chat_url)
    ask(page, VPN_QUESTION)
    wait_for_answer(page, 1)
    page.get_by_role("button", name="🗑 Clear chat").click()
    expect(page.locator(".st-key-welcome")).to_be_visible(timeout=TIMEOUT_MS)
    expect(messages(page)).to_have_count(0)  # waits for the page to settle: a stale message must not linger
    expect(page.get_by_role("button", name="🗑 Clear chat")).to_be_disabled()


# --- 17. a model that cannot be reached -------------------------------------------------------------------------------

@pytest.mark.real
def test_with_the_answer_model_off_the_user_sees_a_friendly_error_not_a_traceback(page: Page, app_url_without_model: str):
    open_app(page, app_url_without_model)
    ask(page, VPN_QUESTION)
    expect(page.get_by_text("I couldn't reach the answer service")).to_be_visible(timeout=ANSWER_TIMEOUT_MS)
    assert no_error_on_page(page)
    expect(chat_box(page)).to_be_enabled()
    assert assistant(page, 1).count() == 0  # no half-written answer was left behind


# --- 18. a reload starts a fresh chat (an idea from the Test Agents' planner and generator) -----------------------------------

def test_reloading_the_page_starts_a_fresh_chat(page: Page, chat_url: str):
    open_app(page, chat_url)
    ask(page, VPN_QUESTION)
    wait_for_answer(page, 1)
    page.reload()
    open_app(page, chat_url)
    expect(page.locator(".st-key-welcome")).to_be_visible(timeout=TIMEOUT_MS)
    expect(messages(page)).to_have_count(0)
    expect(page.get_by_role("button", name="🗑 Clear chat")).to_be_disabled()


# --- 19. the decline gives a way to contact the service desk (an idea from the Test Agents' generator) ------------------------

def test_a_decline_shows_the_service_desk_email_as_a_link(page: Page, chat_url: str):
    open_app(page, chat_url)
    ask(page, "What is the salary band for a senior engineer?")
    wait_for_answer(page, 1)
    link = page.locator(".st-key-answer_1").get_by_role("link", name="servicedesk@northwind.example")
    expect(link).to_have_attribute("href", "mailto:servicedesk@northwind.example", timeout=TIMEOUT_MS)
