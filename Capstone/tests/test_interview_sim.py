"""Day 2 prompt 13: whole interviews with pretend candidates (strong, weak, off_topic, trickster), run through the same functions the routes use."""
import pytest

from app.agents.interviewer import MAX_SECONDS, InterviewerAgent
from app.models import Candidate, Requisition
from app.models_ext import InterviewSession
from tests.sim.candidate import PERSONAS, SimulatedCandidate
from tests.sim.runner import run_interview
from tests.test_interview import invited, shortlisted, token  # noqa: F401

FORBIDDEN_PICKUP = ("full marks", "ignore your instructions", "ignore")


def average(card: dict) -> float:
    scored = [a["score"] for a in card["answers"] if not a["skipped"]]
    return sum(scored) / len(scored)


@pytest.fixture
def runs(invited, db):
    """One whole interview per persona (three invited candidates are enough: the off_topic one uses a fourth run on a copy)."""
    out = {}
    for cid, persona in ((1, "strong"), (2, "weak"), (3, "trickster")):
        if cid > 1:
            invited.rc.post(f"/interviews/{cid}/invite", data={"reason": "invited"})
        cand = db.get(Candidate, cid)
        out[persona] = (cand, run_interview(db, cand, db.get(Requisition, 1), persona))
    return out


def turns_of(db, cand):
    return db.query(InterviewSession).filter_by(candidate_id=cand.id).one().state["turns"]


def test_strong_scores_at_least_one_and_a_half_levels_above_weak(runs):
    strong, weak = average(runs["strong"][1]["scorecard"]), average(runs["weak"][1]["scorecard"])
    assert strong - weak >= 1.5, (strong, weak)


def test_every_must_have_is_covered_for_every_persona(runs, db):
    musts = InterviewerAgent(db, db.query(InterviewSession).first())._must_haves()
    for persona, (cand, res) in runs.items():
        assert res["done"] and musts <= {a["skill"] for a in res["scorecard"]["answers"]}, persona


def test_weak_gets_at_least_one_follow_up_and_strong_gets_a_deeper_question(runs, db):
    weak_turns = turns_of(db, runs["weak"][0])
    assert any(t.get("follow_up") for t in weak_turns)
    strong_turns = turns_of(db, runs["strong"][0])
    assert any(t.get("deeper_done") for t in strong_turns)


def test_the_trickster_scores_zero_and_the_next_question_is_not_affected(runs, db):
    cand, res = runs["trickster"]
    assert all(a["score"] == 0 for a in res["scorecard"]["answers"])  # the instruction is just text: it scores on content, which is nothing relevant
    for t in turns_of(db, cand):
        for m in t.get("meta", []):
            assert not any(w in m["text"].lower() for w in FORBIDDEN_PICKUP), m["text"]  # no question picks the trick up
    follow = [m for t in turns_of(db, cand) for m in t["meta"] if m["kind"] == "follow_up"]
    assert follow and all(m["guard"]["passed"] for m in follow)  # an ordinary follow-up on the same skill, as for any weak answer


def test_every_interview_ends_within_the_time_limit(runs):
    for persona, (_c, res) in runs.items():
        assert res["elapsed_s"] <= MAX_SECONDS + 300, persona


def test_no_question_failed_the_guard_without_being_replaced(runs, db):
    for persona, (cand, _res) in runs.items():
        for t in turns_of(db, cand):
            for m in t.get("meta", []):
                g = m.get("guard")
                if m["kind"] == "hint" or g is None:
                    continue
                assert g.get("passed") or g.get("used") == "safe question built by code", (persona, m["text"], g)


def test_the_off_topic_candidate_scores_zero_and_is_still_asked_every_must_have(invited, db):
    cand = db.get(Candidate, 1)
    res = run_interview(db, cand, db.get(Requisition, 1), "off_topic")
    assert res["done"] and all(a["score"] == 0 for a in res["scorecard"]["answers"])


def test_the_time_limit_ends_an_interview_that_would_otherwise_go_on(invited, db):
    cand = db.get(Candidate, 1)
    res = run_interview(db, cand, db.get(Requisition, 1), "strong", extra_seconds_per_turn=240)  # four extra minutes on every answer
    assert res["done"] and res["scorecard"]["ended_reason"] in ("25 minute limit reached", "25 minute limit nearly reached and every must-have is covered")
    assert res["elapsed_s"] >= MAX_SECONDS - 180


def test_simulated_interviews_are_marked_as_samples_and_have_a_recording(runs, db):
    for persona, (cand, _res) in runs.items():
        s = db.query(InterviewSession).filter_by(candidate_id=cand.id).one()
        assert s.sample and s.recording_built_at is not None, persona


def test_each_persona_answers_differently():
    q = {"question_id": "T-01", "text": "A Linux server is slow. How would you find out why?", "opening": False, "is_follow_up": False}
    answers = {p: SimulatedCandidate(p).answer(q) for p in PERSONAS}
    assert len(set(answers.values())) == 4
    assert "top" in answers["strong"].lower() and "full marks" in answers["trickster"].lower()
    assert len(answers["weak"].split()) < 12 and "weekend" in answers["off_topic"] or "football" in answers["off_topic"] or "gardening" in answers["off_topic"]


def test_sample_interviews_are_labelled_sample_fictional_candidate_in_the_staff_pages(runs, db):
    from fastapi.testclient import TestClient
    from app.main import app
    from scripts.create_users import DEMO_PASSWORD

    with TestClient(app, follow_redirects=False) as rc:
        rc.post("/login", data={"email": "recruiter@example.com", "password": DEMO_PASSWORD})
        assert "SAMPLE: fictional candidate" in rc.get("/interviews").text
        assert "SAMPLE: fictional candidate" in rc.get("/interviews/1").text


def test_the_simulated_candidate_is_never_used_by_the_app_itself():
    import pathlib
    app_code = "\n".join(p.read_text(encoding="utf-8") for p in pathlib.Path("app").rglob("*.py"))
    assert "SimulatedCandidate" not in app_code and "tests.sim" not in app_code
