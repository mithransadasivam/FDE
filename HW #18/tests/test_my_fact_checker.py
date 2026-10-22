"""Day 14 homework: the fact-checker. Run: pytest -q tests/test_my_fact_checker.py"""

import json

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.fact_checker import (
    FACT_CHECKER_PROMPT,
    FactCheck,
    build_team_with_fact_checker,
    fact_check,
    route_with_fact_check,
)
from app.handoffs import HandoffError, Notice, ResearchNotes
from app.team import MAX_REVISIONS
from tests.day11_fakes import says
from tests.day14_fakes import (
    FACTS,
    NOTICE,
    notice_reply,
    research_reply,
    review_reply,
    senders,
    team_client,
)

CONFIG = {"configurable": {"thread_id": "t1"}}
INVENTED = "The portal is expected to be fixed by 10:00."


def check_reply(claims=3, unsupported=()):
    return says(json.dumps({"claims_checked": claims, "unsupported": list(unsupported)}))


def run_team(client, tmp_path):
    app = build_team_with_fact_checker(
        client, tools={}, checkpointer=InMemorySaver(), outbox=str(tmp_path)
    )
    app.invoke({"topic": FACTS["topic"]}, CONFIG)
    return app.get_state(CONFIG).values


def test_fact_check_returns_a_checked_handoff():
    client = team_client(check_reply(4, [f'"{INVENTED}": no fact gives a fix time']))
    result = fact_check(ResearchNotes(**FACTS), Notice(**NOTICE), client)
    assert isinstance(result, FactCheck)
    assert (result.claims_checked, len(result.unsupported)) == (4, 1)
    # the checker is shown both the facts and the draft, and told not to judge style
    user = client.calls[0]["messages"][1]["content"]
    assert "07:58" in user and "Finance Portal unavailable" in user
    assert "Do not judge style" in FACT_CHECKER_PROMPT


def test_a_bad_reply_is_repaired_once_then_fails():
    ok = ResearchNotes(**FACTS), Notice(**NOTICE)
    client = team_client(says("looks fine to me"), check_reply(2))
    assert fact_check(*ok, client).claims_checked == 2
    assert len(client.calls) == 2  # asked again once
    with pytest.raises(HandoffError):
        fact_check(*ok, team_client(says("no"), says("still no")))
    with pytest.raises(ValueError):  # claims_checked cannot be negative
        FactCheck(claims_checked=-1)


def test_an_unsupported_claim_goes_back_to_the_writer_before_review(tmp_path):
    client = team_client(
        research_reply(),
        notice_reply(body=NOTICE["body"] + " " + INVENTED),
        check_reply(4, [f'"{INVENTED}": no fact gives a fix time']),
        notice_reply(),
        check_reply(3),
        review_reply(),
    )
    state = run_team(client, tmp_path)
    assert senders(state)[:6] == [
        "researcher",
        "writer",
        "fact_checker",
        "writer",
        "fact_checker",
        "reviewer",
    ]
    # the writer was told exactly which claim to fix, and INVENTED never reached the reviewer
    assert INVENTED in client.calls[3]["messages"][1]["content"]
    assert INVENTED not in client.calls[5]["messages"][1]["content"]
    assert state["revisions"] == 1 and state["next"] == "human"


def test_a_clean_draft_goes_straight_to_the_reviewer(tmp_path):
    client = team_client(
        research_reply(), notice_reply(), check_reply(3), review_reply()
    )
    state = run_team(client, tmp_path)
    assert senders(state)[:4] == ["researcher", "writer", "fact_checker", "reviewer"]
    assert state["revisions"] == 0 and len(client.calls) == 4


def test_the_route_calls_the_class_rule_first_and_stops_after_max_revisions():
    draft = {"title": "t"}
    base = {"research": {"x": 1}, "draft": draft, "review": None}
    flagged = {"claims_checked": 3, "unsupported": ["x"], "draft": draft}
    # the class rule decides everything except draft -> reviewer
    assert route_with_fact_check({}) == "researcher"
    assert route_with_fact_check({"research": {"x": 1}}) == "writer"
    assert route_with_fact_check({**base, "status": "rejected"}) == "end"
    approved = {"verdict": "approve", "issues": []}
    assert route_with_fact_check({**base, "review": approved}) == "human"
    # a draft with no check, or only a check of an older draft, is checked first
    assert route_with_fact_check(base) == "fact_checker"
    old = {**flagged, "draft": {"title": "older draft"}}
    assert route_with_fact_check({**base, "fact_check": old}) == "fact_checker"
    # unsupported claims go back to the writer, until MAX_REVISIONS is used up
    assert route_with_fact_check({**base, "fact_check": flagged}) == "writer"
    spent = {**base, "fact_check": flagged, "revisions": MAX_REVISIONS}
    assert route_with_fact_check(spent) == "reviewer"
    clean = {**flagged, "unsupported": []}
    assert route_with_fact_check({**base, "fact_check": clean}) == "reviewer"
