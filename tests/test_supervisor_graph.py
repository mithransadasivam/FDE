import pytest
from sqlalchemy import select

from app.agents.base import ToolDenied
from app.models import Candidate, DecisionLog
from app.supervisor_graph import SupervisorAgent, build_graph, checkpointer, routing_rule


@pytest.fixture
def one(platform, db):
    platform.apply("C-001_cv.pdf")
    db.expire_all()
    return platform


def test_routing_rule_in_code():
    assert routing_rule("APPLIED") == "read_cv" and routing_rule("EXTRACTED") == "screen" and routing_rule("SCREENED") == "gate"
    assert routing_rule("DECISION") == "done" and routing_rule("WITHDRAWN") == "done"


def test_supervisor_runs_automatic_steps_then_stops_at_the_shortlist_gate(one, db):
    sup = SupervisorAgent(db)
    out = sup.run(1)
    db.expire_all()
    assert db.get(Candidate, 1).stage == "SCREENED"  # EXTRACTED -> SCREENED was automatic
    assert out["waiting_at_gate"]["gate"] == "recruiter approves the shortlist" and out["waiting_at_gate"]["next"] == "SHORTLISTED"
    assert "move EXTRACTED -> SCREENED" in [e.action for e in db.scalars(select(DecisionLog))]


def test_nothing_passes_a_gate_without_a_person(one, db):
    sup = SupervisorAgent(db)
    sup.run(1)
    out = sup.approve(1, "system", "auto", approved=True)  # the system is not a person
    db.expire_all()
    assert db.get(Candidate, 1).stage == "SCREENED" and "refused" in (out["note"] or "")
    out = sup.approve(1, "recruiter@example.com", "")  # a person without a reason is refused too
    db.expire_all()
    assert db.get(Candidate, 1).stage == "SCREENED"


def test_a_person_walks_the_candidate_through_every_gate(one, db):
    sup = SupervisorAgent(db)
    sup.run(1)
    gates = []
    for why in ("best evidence", "invite", "scorecard reviewed", "second round done"):
        out = sup.approve(1, "recruiter@example.com", why)
        gates.append(out["waiting_at_gate"]["gate"] if out["waiting_at_gate"] else None)
    db.expire_all()
    assert db.get(Candidate, 1).stage == "DECISION" and gates[-1] is None
    moves = [e for e in db.scalars(select(DecisionLog)) if e.action.startswith("move ")]
    assert [m.action.split("-> ")[-1] for m in moves] == ["EXTRACTED", "SCREENED", "SHORTLISTED", "AI_INTERVIEW", "HUMAN_INTERVIEW", "DECISION"]
    assert all("@" in m.actor and m.reason for m in moves if m.action.split("-> ")[-1] in ("SHORTLISTED", "AI_INTERVIEW", "HUMAN_INTERVIEW", "DECISION"))


def test_progress_is_checkpointed_and_resumes_after_a_restart(one, db):
    SupervisorAgent(db).run(1)
    # a brand-new graph object (as after a restart) reads the saved checkpoint and is still waiting at the same gate
    snap = build_graph(checkpointer()).get_state({"configurable": {"thread_id": "candidate-1"}})
    assert snap.next == ("gate",) and snap.tasks[0].interrupts[0].value["gate"] == "recruiter approves the shortlist"
    out = SupervisorAgent(db).run(1)  # running again does not start over
    assert out["waiting_at_gate"]["next"] == "SHORTLISTED"


def test_cannot_score_before_the_rubric_is_approved(platform, db):
    from app.models import Requisition
    platform.apply("C-001_cv.pdf")
    db.get(Requisition, 1).status = "GENERATED"
    db.commit()
    out = SupervisorAgent(db).run(1)
    assert out["waiting_for"] == "hiring manager approves the rubric" and db.get(Candidate, 1).stage == "EXTRACTED"


def test_supervisor_tools_and_least_privilege(one, db):
    sup = SupervisorAgent(db)
    rule = sup.call("routing_rule", stage="SCREENED")
    assert rule["allowed"] == {"SHORTLISTED": "person", "WITHDRAWN": "person"} and rule["gate"]
    assert sup.call("decision_log", limit=3)
    with pytest.raises(ToolDenied):
        sup.call("draft_email", candidate_id=1, kind="update")
    sup.run(1)
    assert sup.call("checkpoint", candidate_id=1)["waiting"]
