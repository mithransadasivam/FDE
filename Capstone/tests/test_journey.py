import json
import sys
from pathlib import Path

from sqlalchemy import select

from app.models import Candidate, DecisionLog
from app.models_ext import FinalDecision, OutboxLog


def test_the_whole_journey_runs_with_every_approval_made_by_a_person(monkeypatch, capsys, db):
    from scripts import run_journey
    monkeypatch.setattr(sys, "argv", ["run_journey", "--quiet"])
    monkeypatch.chdir(Path(__file__).resolve().parent.parent)
    assert run_journey.main() == 0
    out = capsys.readouterr().out
    assert "JOURNEY OK" in out and "decisions, messages or moves without a person: 0" in out
    s = json.loads(Path("evidence/journey.json").read_text(encoding="utf-8"))["summary"]
    assert s["candidates"] == 52 and s["applications_refused"] == 0
    assert s["scores_with_verified_quote"].split("/")[0] == s["scores_with_verified_quote"].split("/")[1]  # every score has a verified quote
    assert s["ai_interviews_done"] >= 5 and s["asked_for_a_person"] == 1 and s["copilot_interviews"] == 4
    assert [d for d, _ in s["final_decisions"]] == ["ADVANCE", "NOT_THIS_TIME", "HOLD", "ADVANCE"]
    assert all(a == "recruiter@example.com" for _, a in s["final_decisions"])
    assert s["emails_waiting"] == 0 and s["emails_sent_after_approval"] >= 10


def test_in_the_journey_every_stage_move_to_a_decision_stage_has_a_person_and_a_reason(db):
    from app.db import SessionLocal
    with SessionLocal() as s:
        if s.query(Candidate).count() == 0:
            return  # the journey test above fills the database; run alone this test has nothing to check
        for e in s.scalars(select(DecisionLog)):
            if e.action.startswith("move ") and e.action.split("-> ")[-1] in ("SHORTLISTED", "AI_INTERVIEW", "HUMAN_INTERVIEW", "DECISION"):
                assert "@" in e.actor and e.reason.strip(), e.action
        assert all("@" in o.approved_by for o in s.scalars(select(OutboxLog)))
        assert all("@" in d.actor for d in s.scalars(select(FinalDecision)))
