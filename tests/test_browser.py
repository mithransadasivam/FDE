"""Playwright tests: a real browser plays recorded audio into the interview page and the copilot panel and checks what appears (Day 4, role B).

The server runs in a thread against the test database. Recorded answers are played from the fixtures (fake mode); the browser's microphone is not needed.
"""
import socket
import threading
import time

import pytest
import uvicorn

playwright = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect, sync_playwright  # noqa: E402

from app.main import app  # noqa: E402
from app.models import Candidate  # noqa: E402

ORDER = ["C-001_cv.pdf", "C-002_cv.pdf", "C-011_cv.docx", "C-004_cv.docx"]


@pytest.fixture
def live(platform, db):
    for f in ORDER:
        platform.apply(f)
    platform.rc.post("/screening/1/run")
    platform.rc.post("/screening/1/approve", data={"reason": "best evidence", "candidate_id": [1, 2, 3, 4]})
    for cid in (1, 2, 3, 4):
        platform.rc.post(f"/interviews/{cid}/invite")
    for cid in (3, 4):  # candidates 3 and 4 go on to a human interview (recordings H-3 and H-4)
        platform.rc.post(f"/interviews/{cid}/replay", data={"quality": "strong"})
        platform.rc.post(f"/copilot/{cid}/to-human-interview")
    db.expire_all()
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    yield f"http://127.0.0.1:{port}", {c.id: c.access_token for c in db.query(Candidate)}
    server.should_exit = True
    thread.join(timeout=10)


@pytest.fixture
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


def test_interview_page_notice_diagram_recorded_answers_and_scorecard(live, browser):
    base, tokens = live
    page = browser.new_page()
    page.goto(f"{base}/interview/{tokens[1]}")
    expect(page.get_by_test_id("notice")).to_contain_text("You are talking to an AI interviewer")
    expect(page.get_by_test_id("person-btn")).to_be_visible()  # the candidate can always ask for a person
    page.get_by_test_id("start-btn").click()
    expect(page.get_by_test_id("question-text")).not_to_be_empty()
    seen_diagram, seen_follow_up, answered = False, False, 0
    while answered < 20:
        if page.get_by_test_id("done-msg").is_visible():
            break
        question = page.get_by_test_id("question-text").inner_text()
        seen_follow_up = seen_follow_up or "(follow-up)" in page.get_by_test_id("progress").inner_text()
        if page.get_by_test_id("diagram").is_visible():
            seen_diagram = True
            assert page.get_by_test_id("diagram").evaluate("el => el.complete && el.naturalWidth > 0")  # the image really loaded
        options = page.locator("[data-testid=fixture-select] option:not([hidden])")
        if options.count() == 0 or "follow-up" in page.get_by_test_id("progress").inner_text():
            page.get_by_test_id("answer-text").fill("I would also check the logs and what changed recently.")
            page.get_by_test_id("send-answer").click()
        else:
            sel = page.get_by_test_id("fixture-select")  # play the PARTIAL recorded answer, so a follow-up is needed
            partial = sel.evaluate("el => { const o = [...el.options].find(o => !o.hidden && o.textContent.includes('partial')); return o ? o.value : null; }")
            if partial:
                sel.select_option(partial)
            page.get_by_test_id("play-fixture").click()
        answered += 1
        expect(page.get_by_test_id("transcript")).not_to_have_text("(nothing yet)")
        try:
            page.wait_for_function("q => document.querySelector('[data-testid=question-text]').textContent !== q || document.querySelector('[data-testid=done-msg]').offsetParent !== null", arg=question, timeout=15000)
        except Exception:
            raise AssertionError("page did not advance after answer %d. Progress=%r Question=%r Transcript=%r" % (answered, page.get_by_test_id("progress").inner_text(), question, page.get_by_test_id("transcript").inner_text()))
    expect(page.get_by_test_id("done-msg")).to_be_visible(timeout=15000)
    assert seen_diagram and seen_follow_up and 8 <= answered <= 16


def test_interview_page_ask_for_a_person_instead(live, browser):
    base, tokens = live
    page = browser.new_page()
    page.goto(f"{base}/interview/{tokens[2]}")
    page.on("dialog", lambda d: d.accept())
    page.get_by_test_id("person-btn").click()
    expect(page.get_by_test_id("person-requested")).to_be_visible()
    expect(page.get_by_test_id("person-requested")).to_contain_text("A person will interview you")


def test_interview_page_refuses_a_candidate_who_was_not_invited(platform, db, browser):
    platform.apply("C-007_cv.pdf")
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning"))
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    try:
        page = browser.new_page()
        page.goto(f"http://127.0.0.1:{port}/interview/{db.get(Candidate, 1).access_token}")
        expect(page.get_by_test_id("not-invited")).to_contain_text("not been invited")
    finally:
        server.should_exit = True
        t.join(timeout=10)


def sign_in_as_recruiter(page, base):
    page.goto(f"{base}/login")
    page.fill("#email", "recruiter@example.com")
    page.fill("#password", "demo-password-1")
    page.click("button[type=submit]")
    expect(page).to_have_url(f"{base}/")


def test_copilot_panel_follows_the_interview_and_warns_about_a_forbidden_question(live, browser):
    base, _ = live
    page = browser.new_page()
    sign_in_as_recruiter(page, base)
    page.goto(f"{base}/copilot/4")  # candidate 4 = recording H-4: the recruiter asks about children
    expect(page.get_by_test_id("copilot-notice")).to_contain_text("Tell the candidate first")
    page.get_by_test_id("ack-btn").click()
    page.select_option("#speed", "0")
    page.get_by_test_id("start-replay").click()
    warning = page.get_by_test_id("warning")
    expect(warning).to_be_visible(timeout=20000)
    expect(warning).to_contain_text("must not be asked")
    transcript = page.get_by_test_id("transcript")
    expect(transcript).to_contain_text("RECRUITER")
    expect(transcript).to_contain_text("CANDIDATE")
    expect(transcript).to_contain_text("Do you have children?")
    expect(page.get_by_test_id("suggestions")).to_contain_text("technical")  # suggestions appear
    expect(page.get_by_test_id("draft")).to_be_visible(timeout=20000)
    expect(page.get_by_test_id("draft")).to_contain_text("draft")


def test_copilot_panel_ticks_key_points_and_shows_a_cv_check(live, browser):
    base, _ = live
    page = browser.new_page()
    sign_in_as_recruiter(page, base)
    page.goto(f"{base}/copilot/3")  # candidate 3 = recording H-3: the CV conflict about Kubernetes
    page.get_by_test_id("ack-btn").click()
    page.select_option("#speed", "0")
    page.get_by_test_id("start-replay").click()
    expect(page.get_by_test_id("cvcheck")).to_contain_text("Kubernetes", timeout=20000)
    expect(page.get_by_test_id("cvcheck")).to_contain_text("Consider asking")
    expect(page.get_by_test_id("points")).to_contain_text("✓")  # at least one key point was ticked
    expect(page.get_by_test_id("coverage")).to_contain_text("covered")
    assert not page.get_by_test_id("warning").is_visible()  # no forbidden question in this interview


def test_assistant_streams_an_answer_with_sources_in_the_browser(live, browser):
    base, _ = live
    page = browser.new_page()
    sign_in_as_recruiter(page, base)
    page.goto(f"{base}/assistant")
    page.get_by_test_id("question").fill("Who has run Kubernetes in production?")
    page.get_by_test_id("ask-btn").click()
    expect(page.get_by_test_id("answer")).to_contain_text("candidate", timeout=15000)
    expect(page.get_by_test_id("sources").locator("li").first).to_contain_text("Candidate #", timeout=15000)
