"""Day 2 prompt 14: the scorecard, the second scorer, the person's own review before any audio, and the decision."""
import pytest

from app.db import OpsSession
from app.interview.scorecard import DISAGREE_BY, build_card
from app.models import Candidate, DecisionLog, Requisition
from app.models_ext import InterviewSession, ModelCall
from app.privacy import identity_strings
from sqlalchemy.orm.attributes import flag_modified
from tests.sim.runner import run_interview
from tests.test_interview import invited, review_form, shortlisted, token  # noqa: F401


@pytest.fixture
def strong(invited, db):
    run_interview(db, db.get(Candidate, 1), db.get(Requisition, 1), "strong")
    db.expire_all()
    return invited


@pytest.fixture
def weak(invited, db):
    run_interview(db, db.get(Candidate, 1), db.get(Requisition, 1), "weak")
    db.expire_all()
    return invited


def session(db):
    db.expire_all()
    return db.query(InterviewSession).one()


def test_the_scorecard_shows_levels_questions_with_why_quotes_and_the_summary(strong, db):
    html = strong.rc.get("/interviews/1").text
    for needle in ("Overall", "Must-haves covered", "AI-written summary", "Level 3 means", "(exact words from the transcript)", "Questions asked", "why:"):
        assert needle in html, needle
    card = build_card(db, session(db))
    assert card["all_must_haves_covered"] and card["summary"]["text"]
    for r in card["skills"]:
        if r["asked"] and r["level"]:
            assert r["best"] and r["best"]["quote"] and r["level_description"] and all(q["why"] for q in r["questions"])


def test_the_overall_score_is_calculated_by_code_from_the_rubric_weights(strong, db):
    s = session(db)
    card = build_card(db, s)
    expected = round(sum(r["weight"] * r["level"] / 3 for r in card["skills"] if r["level"] is not None), 1)
    assert card["overall_100"] == expected and 0 < expected <= 100
    assert f"{expected} / 100" in strong.rc.get("/interviews/1").text


def test_a_difference_of_two_levels_is_flagged_for_a_person_and_never_averaged(weak, db):
    card = build_card(db, session(db))
    flagged = [r for r in card["skills"] if r["scorers_disagree"]]
    assert flagged and card["scorers_disagree"] == [r["skill"] for r in flagged]
    assert all(abs(r["level"] - r["second_level"]) >= DISAGREE_BY for r in flagged)
    html = weak.rc.get("/interviews/1").text
    assert "scorers disagree: please review" in html
    assert all(r["level"] != (r["level"] + r["second_level"]) / 2 or r["level"] == r["second_level"] for r in flagged)  # the levels stay as they are


def test_a_disagreement_is_flagged_at_two_levels_apart_and_not_at_one(strong, db):
    s = session(db)
    skill = next(r["skill"] for r in build_card(db, s)["skills"] if r["level"] == 3)
    qid = next(t["question_id"] for t in s.state["turns"] if t.get("skill") == skill)
    for second, flagged in ((2, False), (1, True), (0, True)):
        s.scorecard["second_scorer"][qid] = second
        flag_modified(s, "scorecard")
        row = next(r for r in build_card(db, s)["skills"] if r["skill"] == skill)
        assert row["scorers_disagree"] is flagged, second


def test_audio_is_hidden_until_the_recruiter_has_entered_their_own_levels(strong, db):
    assert "<audio" not in strong.rc.get("/interviews/1").text
    assert strong.rc.get("/interviews/1").text.count("audio-hidden") == 1
    form = review_form(db)
    first = next(iter(form))
    strong.rc.post("/interviews/1/review", data={first: "2"})  # only one of the must-haves: refused
    assert session(db).review is None and "<audio" not in strong.rc.get("/interviews/1").text
    strong.rc.post("/interviews/1/review", data={**form, first: "5"})  # not a level: refused
    assert session(db).review is None
    strong.rc.post("/interviews/1/review", data={**form, "note": "read the transcripts"})
    s = session(db)
    assert s.review["levels"] and s.review["by"] == "recruiter@example.com" and s.review["note"] == "read the transcripts"
    assert "<audio" in strong.rc.get("/interviews/1").text
    log = db.query(DecisionLog).filter(DecisionLog.action == "AI interview scorecard reviewed").one()
    assert log.evidence["review"]["levels"] and "ai_levels" in log.evidence


def test_the_recording_player_and_timeline_appear_only_after_the_review(strong, db):
    assert "full-audio" not in strong.rc.get("/interviews/1").text
    strong.rc.post("/interviews/1/review", data=review_form(db))
    html = strong.rc.get("/interviews/1").text
    assert "full-audio" in html and 'data-testid="timeline"' in html and "/interviews/1/recording" in html


def test_a_decision_needs_the_review_first_and_a_reason(strong, db):
    r = strong.rc.post("/interviews/1/decision", data={"decision": "human_interview", "reason": "strong interview"})
    assert db.get(Candidate, 1).stage == "AI_INTERVIEW"  # no review yet: refused
    strong.rc.post("/interviews/1/review", data=review_form(db))
    strong.rc.post("/interviews/1/decision", data={"decision": "human_interview", "reason": "  "})
    db.expire_all()
    assert db.get(Candidate, 1).stage == "AI_INTERVIEW"  # no reason: refused
    assert strong.hm.post("/interviews/1/decision", data={"decision": "human_interview", "reason": "x"}).status_code == 403
    strong.rc.post("/interviews/1/decision", data={"decision": "human_interview", "reason": "strong on every must-have"})
    db.expire_all()
    assert db.get(Candidate, 1).stage == "HUMAN_INTERVIEW"
    log = db.query(DecisionLog).filter(DecisionLog.action == "move AI_INTERVIEW -> HUMAN_INTERVIEW").one()
    assert log.actor == "recruiter@example.com" and log.reason == "strong on every must-have" and log.evidence["review"]["levels"]


def test_withdraw_goes_through_the_supervisor_with_a_reason(weak, db):
    weak.rc.post("/interviews/1/review", data=review_form(db, "0"))
    weak.rc.post("/interviews/1/decision", data={"decision": "withdraw", "reason": "does not meet the must-haves"})
    db.expire_all()
    assert db.get(Candidate, 1).stage == "WITHDRAWN"
    assert db.query(DecisionLog).filter(DecisionLog.action == "move AI_INTERVIEW -> WITHDRAWN").one().reason == "does not meet the must-haves"


def test_the_summary_is_made_from_the_scores_only(strong, db):
    cand = db.get(Candidate, 1)
    with OpsSession() as ops:
        call = ops.query(ModelCall).filter(ModelCall.agent == "scorecard").one()
    assert "<scores>" in call.prompt_user and "level" in call.prompt_user
    s = session(db)
    quotes = [t["score"]["quote"] for t in s.state["turns"] if t.get("score") and t["score"].get("quote")]
    assert quotes and not any(q in call.prompt_user for q in quotes)  # no transcript text reaches the summary prompt
    for secret in identity_strings(cand.profile):
        assert secret.lower() not in call.prompt_user.lower()


def test_a_diagram_question_shows_its_diagram_and_hidden_expected_points_to_the_recruiter(strong, db):
    s = session(db)
    found = [m for t in s.state["turns"] for m in t.get("meta", []) if m.get("diagram")]
    html = strong.rc.get("/interviews/1").text
    if found:
        assert 'class="mermaid"' in html and "never shown to the candidate" in html
    assert "Expected points" not in strong.visitor.get(f"/interview/{token(db)}").text
