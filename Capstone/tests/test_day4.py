import pytest

from app.agents.communications import approve_and_send
from app.decisions import build_scorecard, decide, explain_not_shortlisted, recommendation
from app.models import Candidate, DecisionLog
from app.models_ext import EmailDraft, ExplanationRequest, FinalDecision, OutboxLog
from app.supervisor import MoveRefused

ORDER = ["C-001_cv.pdf", "C-002_cv.pdf", "C-011_cv.docx", "C-004_cv.docx"]


@pytest.fixture
def journey(platform, db):
    for f in ORDER:
        platform.apply(f)
    platform.rc.post("/screening/1/run")
    platform.rc.post("/screening/1/approve", data={"reason": "best evidence", "candidate_id": [1, 2, 3, 4]})
    for cid in (1, 2, 3, 4):
        platform.rc.post(f"/interviews/{cid}/invite")
        platform.rc.post(f"/interviews/{cid}/replay", data={"quality": "strong"})
        platform.rc.post(f"/interviews/{cid}/review")
        platform.rc.post(f"/copilot/{cid}/to-human-interview")
        platform.rc.post(f"/copilot/{cid}/ack")
        platform.rc.get(f"/copilot/{cid}/events", params={"speed": 0})
    db.expire_all()
    return platform


def test_scorecard_shows_every_score_quote_and_link_to_the_moment(journey, db):
    html = journey.rc.get("/scorecard/1").text
    assert "CV scores" in html and "&ldquo;Linux&rdquo;" in html and "AI first-round interview" in html
    assert "/media/interview/1?ref=" in html  # link to the AI interview recording
    assert "/copilot/1/audio#t=" in html  # link to the moment in the human interview recording
    assert "Recommendation" in html and "AI suggests" in html
    card = build_scorecard(db, db.get(Candidate, 1))
    assert card["checks"]["every_score_has_a_quote"] and card["human_interview"]["moments"] and card["ai_interview"]["total"] > 0


def test_hiring_manager_sees_the_scorecard_blind_with_no_decision_form_or_audio(journey):
    html = journey.hm.get("/scorecard/1").text
    assert "CV scores" in html and "amara.okafor" not in html and "Amara" not in html and "+44" not in html
    assert "decision-form" not in html and "/media/interview" not in html and "/copilot/1/audio" not in html


def test_the_recruiter_records_a_decision_with_a_reason_and_it_is_logged(journey, db):
    r = journey.rc.post("/scorecard/1/decide", data={"decision": "ADVANCE", "reason": ""})
    db.expire_all()
    assert db.get(Candidate, 1).stage == "HUMAN_INTERVIEW" and db.query(FinalDecision).count() == 0  # no reason: refused
    assert journey.hm.post("/scorecard/1/decide", data={"decision": "ADVANCE", "reason": "x" * 5}).status_code == 403
    journey.rc.post("/scorecard/1/decide", data={"decision": "ADVANCE", "reason": "Strong evidence in both interviews"})
    db.expire_all()
    fd = db.query(FinalDecision).one()
    assert fd.actor == "recruiter@example.com" and fd.decision == "ADVANCE" and fd.evidence["cv_total"] > 0
    assert db.get(Candidate, 1).stage == "DECISION"
    log = db.query(DecisionLog).filter_by(action="final decision: ADVANCE").one()
    assert log.reason == "Strong evidence in both interviews" and log.evidence["recommendation"]
    assert "Decision: ADVANCE" in journey.rc.get("/scorecard/1").text


def test_the_decision_email_is_drafted_but_never_sent_without_approval(journey, db):
    before = db.query(OutboxLog).count()
    journey.rc.post("/scorecard/2/decide", data={"decision": "NOT_THIS_TIME", "reason": "Gaps in networking and incident handling"})
    db.expire_all()
    d = db.query(EmailDraft).filter_by(candidate_id=2, kind="decision").one()
    assert d.status == "DRAFT" and "will not be taking" in d.body and db.query(OutboxLog).count() == before
    journey.rc.post(f"/outbox/{d.id}/approve")
    db.expire_all()
    assert db.get(EmailDraft, d.id).status == "SENT"


def test_decision_values_and_stage_are_enforced(journey, db):
    cand = db.get(Candidate, 3)
    with pytest.raises(MoveRefused, match="not a decision"):
        decide(db, cand, "HIRE_NOW", "because", "recruiter@example.com")
    with pytest.raises(Exception):
        decide(db, cand, "ADVANCE", "ok", "system")  # the system cannot decide (supervisor refuses)
    db.rollback()
    assert db.get(Candidate, 3).stage == "HUMAN_INTERVIEW"


def test_recommendation_is_only_a_suggestion():
    assert recommendation([], None) == "Not scored yet."


# ---- explanation on request (BR-19) -----------------------------------------------------------------------------------------------------
def test_a_candidate_not_shortlisted_can_ask_why_and_a_recruiter_reviews_it_first(platform, db):
    for f in ORDER:
        platform.apply(f)
    platform.rc.post("/screening/1/run")
    platform.rc.post("/screening/1/approve", data={"reason": "best two", "candidate_id": [1, 3]})
    t = db.get(Candidate, 2).access_token
    page = platform.visitor.get(f"/me/{t}").text
    assert "Why was I not shortlisted?" in page
    platform.visitor.post(f"/me/{t}/explain")
    db.expire_all()
    req = db.query(ExplanationRequest).one()
    d = db.get(EmailDraft, req.draft_id)
    assert d.kind == "explanation" and d.status == "DRAFT" and "recruiter" in d.body.lower() and "more evidence of" in d.body
    assert "@example.com" not in d.body and "score" not in d.body.lower().replace("scored", "")  # plain words, no private details
    assert db.query(OutboxLog).count() == 0  # nothing is sent until a recruiter approves it
    platform.rc.post(f"/outbox/{d.id}/approve")
    db.expire_all()
    assert db.query(OutboxLog).count() == 1


def test_a_shortlisted_candidate_is_not_offered_the_explanation(platform, db):
    platform.apply("C-001_cv.pdf")
    platform.rc.post("/screening/1/run")
    platform.rc.post("/screening/1/approve", data={"reason": "ok", "candidate_id": [1]})
    assert "Why was I not shortlisted?" not in platform.visitor.get(f"/me/{db.get(Candidate, 1).access_token}").text


def test_nothing_to_explain_before_scoring(platform, db):
    platform.apply("C-001_cv.pdf")
    with pytest.raises(MoveRefused):
        explain_not_shortlisted(db, db.get(Candidate, 1))


# ---- the Trust & cost tab -----------------------------------------------------------------------------------------------------------------------
def test_trust_tab_shows_the_quality_bar_costs_and_live_checks(journey):
    html = journey.rc.get("/trust").text
    for name in ("The quality bar", "CV extraction", "Identity hidden", "Evidence", "Forbidden question", "Red team", "Approvals", "Governance",
                 "Cost per 100 CVs screened", "Cost per AI interview", "By agent", "Agent steps"):
        assert name in html, name
    assert journey.hm.get("/trust").status_code == 200 and journey.visitor.get("/trust").status_code == 303


def test_live_checks_pass_after_a_clean_journey(journey, db):
    from app.web.trust import quality_bar
    bar = {r["what"]: r for r in quality_bar(db)}
    assert bar["Identity hidden"]["passed"] and bar["Evidence"]["passed"] and bar["Approvals"]["passed"]
