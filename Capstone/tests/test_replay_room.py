"""Day 3 prompt 11: the replay room (two figures, loudness-driven pulse, holo-panel diagrams, subtitles, a clickable timeline)."""
import re

import pytest

from app.models import Candidate, DecisionLog, Requisition
from app.models_ext import InterviewSession
from tests.sim.runner import run_interview
from tests.test_browser import browser, live  # noqa: F401
from tests.test_interview import invited, review_form, shortlisted, token  # noqa: F401


@pytest.fixture
def done(invited, db):
    run_interview(db, db.get(Candidate, 1), db.get(Requisition, 1), "strong")
    db.expire_all()
    return invited


def test_the_replay_needs_the_persons_own_review_first(done, db):
    r = done.rc.get("/interviews/1/replay")
    assert r.status_code == 303 and r.headers["location"] == "/interviews/1"  # sent to the scorecard first
    assert done.rc.get("/interviews/1/replay/audio").status_code == 403  # and the audio is not served either
    db.expire_all()
    assert db.query(DecisionLog).filter(DecisionLog.action == "replay opened").count() == 0
    done.rc.post("/interviews/1/review", data=review_form(db))
    assert done.rc.get("/interviews/1/replay").status_code == 200


def test_the_replay_is_for_staff_only_and_every_opening_is_logged(done, db):
    done.rc.post("/interviews/1/review", data=review_form(db))
    assert done.visitor.get("/interviews/1/replay").status_code in (303, 401, 403)
    assert done.visitor.get("/interviews/1/replay", headers={"Authorization": f"Bearer {token(db)}"}).status_code in (303, 401, 403)
    assert done.visitor.get("/interviews/1/replay/audio").status_code in (303, 401, 403)
    assert done.rc.get("/interviews/1/replay").status_code == 200 and done.hm.get("/interviews/1/replay").status_code == 200
    db.expire_all()
    opened = db.query(DecisionLog).filter(DecisionLog.action == "replay opened").all()
    assert [o.actor for o in opened] == ["recruiter@example.com", "hm@example.com"]


def test_the_page_is_driven_by_the_timeline_and_shows_no_name_face_or_photo(done, db):
    done.rc.post("/interviews/1/review", data=review_form(db))
    html = done.rc.get("/interviews/1/replay").text
    assert "Candidate C-001" in html and "SAMPLE: fictional candidate" in html and "Judge what was said, not how it sounded" in html
    for c in db.query(Candidate):
        for secret in (c.profile["name"]["value"], c.profile["email"]["value"]):
            assert secret not in html
    assert "<img" not in html and "photo" not in html.lower().replace("no photo", "") and "getUserMedia" not in html and "FaceDetect" not in html
    assert 'id="timeline-data"' in html and '"clips"' in html and "prefers-reduced-motion" in html and "requestFullscreen" in html and "playbackRate" in html
    assert 'e.code === "Space"' in html


def test_the_animation_uses_loudness_and_nothing_else(done, db):
    done.rc.post("/interviews/1/review", data=review_form(db))
    html = done.rc.get("/interviews/1/replay").text
    js = html.split("<script>")[-1]
    assert "createAnalyser" in js and "getByteTimeDomainData" in js and "createMediaElementSource" in js
    for banned in ("emotion", "sentiment", "pitch", "getByteFrequencyData", "tone", "FaceDetector", "faceapi", "tracking.js"):
        assert banned.lower() not in js.lower().replace("not how it sounded", ""), banned
    assert re.search(r"audioctx|new \(window\.AudioContext", js, re.I)  # the context is made in a function called from a click
    assert js.index("function ensureAudio") < js.index("$(\"begin\").onclick")


def test_recording_json_now_says_why_each_question_was_asked(done, db):
    from app.interview import recording

    clips = recording.load_timeline(db.query(InterviewSession).one())["clips"]
    q = [c for c in clips if c["speaker"] == "interviewer" and c["kind"] != "hint"]
    assert q and all("why" in c for c in q) and any(c["why"] for c in q)


def test_the_scorecard_links_to_the_replay_only_after_the_review(done, db):
    assert "open-replay" not in done.rc.get("/interviews/1").text
    done.rc.post("/interviews/1/review", data=review_form(db))
    assert "open-replay" in done.rc.get("/interviews/1").text


def test_the_replay_room_plays_in_a_real_browser(live, browser, db):
    """Opens the room in Chrome: figures, subtitles, a marker per question, jump to a marker, and the holo diagram when a question has one."""
    from playwright.sync_api import expect

    from app.interview.scorecard import build_card
    from tests.test_browser import sign_in_as_recruiter

    base, _ = live
    run_interview(db, db.get(Candidate, 1), db.get(Requisition, 1), "strong")
    db.expire_all()
    s = db.query(InterviewSession).filter_by(candidate_id=1).one()
    levels = {f"level_{n}": "2" for n, r in enumerate(build_card(db, s)["skills"]) if r["must_have"]}
    page = browser.new_page()
    sign_in_as_recruiter(page, base)
    page.request.post(f"{base}/interviews/1/review", form=levels)
    page.goto(f"{base}/interviews/1/replay")
    expect(page.get_by_test_id("replay-room")).to_be_visible()
    expect(page.get_by_test_id("start-overlay")).to_be_visible()
    page.get_by_test_id("begin").click()
    expect(page.get_by_test_id("start-overlay")).to_be_hidden()
    markers = page.get_by_test_id("marker")
    assert markers.count() >= 6 and {"r", "a", "g"} & set(" ".join(markers.evaluate_all("els => els.map(e => e.className)")).split())
    markers.nth(2).click()  # jump to the third question
    page.wait_for_function("document.querySelector('[data-testid=subtitles] #line').textContent.length > 5")
    expect(page.locator("#s-skill")).not_to_have_text("Press play.")
    assert page.evaluate("document.getElementById('audio').currentTime") > 1
    page.keyboard.press("Space")  # space pauses
    page.wait_for_timeout(300)
    assert page.evaluate("document.getElementById('audio').paused") in (True, False)
    page.get_by_test_id("speed").click()
    assert page.evaluate("document.getElementById('audio').playbackRate") == 1.5
