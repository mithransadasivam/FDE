"""Day 2 prompt 10: diagrams drawn on the fly as Mermaid text, checked by code, limited to 3, expected points hidden from the candidate."""
import json

import pytest

from app.agents import diagrams as D
from app.agents.interviewer import InterviewerAgent, NextQuestion, get_or_create_session
from app.models import Candidate, Requisition
from app.models_ext import InterviewTurn
from tests.test_browser import browser, live  # noqa: F401  (a real browser against a live server)
from tests.test_interview import invited, shortlisted, token  # noqa: F401

GOOD = "flowchart LR\n  U[Users] --> LB[Load balancer]\n  LB --> A[App server]\n  A --> DB[(Database)]"


@pytest.fixture(autouse=True)
def clean():
    D.FORCE_DIAGRAM.clear()
    yield
    D.FORCE_DIAGRAM.clear()


def test_validation_rules():
    assert D.validate_mermaid(GOOD) == []
    assert any("start with" in p for p in D.validate_mermaid("sequenceDiagram\n  A->>B: hi"))
    assert any("3 nodes" in p for p in D.validate_mermaid("flowchart LR\n  A --> B\n  B --> C"))
    many = "flowchart TD\n" + "\n".join(f"  N{i} --> N{i + 1}" for i in range(13))
    assert any("14 nodes" in p for p in D.validate_mermaid(many))
    assert any("real company" in p for p in D.validate_mermaid("flowchart LR\n  U[Users] --> G[Google load balancer]\n  G --> A[App]\n  A --> DB[(Database)]"))
    assert any("not a plain diagram" in p for p in D.validate_mermaid(GOOD + "\n  click A javascript:alert(1)"))


def test_the_default_fake_diagram_is_a_valid_small_web_app_with_one_weakness():
    d = D.make_diagram("a small web application", "Resilience")
    assert d and D.validate_mermaid(d.mermaid) == [] and "single database" in d.weakness.lower() and 3 <= len(d.expected_points) <= 5
    assert "load balancer" in d.mermaid.lower() and d.mermaid.count("App server") == 2


def test_a_broken_diagram_is_retried_once_then_used_if_the_retry_is_good():
    D.FORCE_DIAGRAM.append("not a diagram at all")
    d = D.make_diagram("x", "Resilience")
    assert d is not None and D.validate_mermaid(d.mermaid) == []


def test_a_diagram_that_stays_broken_is_dropped():
    D.FORCE_DIAGRAM.extend(["not a diagram", "flowchart LR\n  A --> B"])
    assert D.make_diagram("x", "Resilience") is None


@pytest.fixture
def agent(invited, db):
    s = get_or_create_session(db, db.get(Candidate, 1))
    s.notice_ack = True
    db.commit()
    a = InterviewerAgent(db, s)
    a.start(db.get(Requisition, 1))
    return a


def want_diagram(skill="Kubernetes"):
    return NextQuestion(skill=skill, kind="technical", text="How would you design this?", why="t", needs_diagram=True, diagram_brief="a cluster")


def test_at_most_three_diagrams_per_interview(agent):
    results = [agent._diagram_for(want_diagram()) for _ in range(5)]
    assert [shown is not None for shown, _ in results] == [True, True, True, False, False]
    assert agent.session.state["diagrams_used"] == 3


def test_a_question_that_does_not_need_a_diagram_gets_none(agent):
    nq = want_diagram()
    nq.needs_diagram = False
    assert agent._diagram_for(nq) == (None, None)


def test_the_diagram_and_its_expected_points_are_saved_on_the_turn_but_never_sent_to_the_candidate(agent, db):
    shown, hidden = agent._diagram_for(want_diagram())
    turn = agent.session.state["turns"][-1]
    agent._ask(turn, "How would you design this?", "technical", why="test", diagram=shown, diagram_info=hidden)
    agent._save()
    row = db.query(InterviewTurn).order_by(InterviewTurn.n.desc()).first()
    assert row.diagram == shown["text"] and row.diagram_info["expected_points"] and row.diagram_info["weakness"]
    prompt = agent.next_prompt()
    assert prompt["mermaid"] == shown
    wire = json.dumps(prompt)  # what the page receives
    assert hidden["weakness"] not in wire and hidden["expected_points"][0] not in wire and "expected_points" not in wire


def test_in_a_real_interview_design_questions_can_carry_a_diagram(invited, db):
    """An extra question on a design skill (not one with a picture of its own) is written with a Mermaid diagram."""
    from app.interview.replay import load_recorded, run_recorded_interview

    run_recorded_interview(db, db.get(Candidate, 1), db.get(Requisition, 1), "partial")
    db.expire_all()
    rows = db.query(InterviewTurn).filter(InterviewTurn.diagram.is_not(None)).all()
    assert len(rows) <= 3
    for r in rows:
        assert D.validate_mermaid(r.diagram) == [] and r.diagram_info["expected_points"]


def test_the_browser_draws_the_mermaid_diagram_beside_the_question(live, browser, db):
    from playwright.sync_api import expect
    from sqlalchemy.orm.attributes import flag_modified

    base, tokens = live
    page = browser.new_page()
    page.goto(f"{base}/interview/{tokens[1]}")
    page.get_by_test_id("consent-box").check()
    page.get_by_test_id("start-btn").click()
    expect(page.get_by_test_id("question-text")).not_to_be_empty()
    s = get_or_create_session(db, db.get(Candidate, 1))
    a = InterviewerAgent(db, s)
    shown, hidden = a._diagram_for(want_diagram())
    s.state["turns"][-1]["meta"][-1]["diagram"], s.state["turns"][-1]["meta"][-1]["diagram_info"] = shown, hidden
    flag_modified(s, "state")
    db.commit()
    page.reload()
    expect(page.get_by_test_id("mermaid-diagram").locator("svg")).to_be_visible(timeout=15000)
    assert "expected" not in page.content().lower() and hidden["weakness"] not in page.content()
