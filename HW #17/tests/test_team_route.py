"""Activity 2: route() is the supervisor's rule for who works next. Run: pytest tests/test_team_route.py"""

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from app.team import MAX_REVISIONS, MAX_STEPS, build_team, route
from tests.day14_fakes import (
    notice_reply,
    research_reply,
    review_reply,
    senders,
    team_client,
)

DRAFT = {"title": "t"}
OK = {"verdict": "approve", "issues": []}
REVISE = {"verdict": "revise", "issues": ["Say when the next update is"]}


@pytest.mark.parametrize(
    "state, expected",
    [
        ({"topic": "x"}, "researcher"),
        ({"topic": "x", "research": {"facts": []}, "draft": None}, "writer"),
        ({"research": {"f": 1}, "draft": DRAFT}, "reviewer"),
        ({"research": {"f": 1}, "draft": DRAFT, "review": REVISE}, "writer"),
        (
            {
                "research": {"f": 1},
                "draft": DRAFT,
                "review": REVISE,
                "revisions": MAX_REVISIONS,
            },
            "human",
        ),
        ({"research": {"f": 1}, "draft": DRAFT, "review": OK}, "human"),
        (
            {
                "research": {"f": 1},
                "draft": DRAFT,
                "review": OK,
                "human": {"decision": "approve"},
            },
            "publish",
        ),
        (
            {
                "research": {"f": 1},
                "draft": DRAFT,
                "review": OK,
                "human": {"decision": "revise"},
                "revisions": 1,
            },
            "writer",
        ),
        (
            {
                "research": {"f": 1},
                "draft": DRAFT,
                "review": OK,
                "human": {"decision": "revise"},
                "revisions": MAX_REVISIONS,
            },
            "end",
        ),
        (
            {
                "research": {"f": 1},
                "draft": DRAFT,
                "review": OK,
                "human": {"decision": "reject"},
            },
            "end",
        ),
    ],
)
def test_each_rule(state, expected):
    assert route(state) == expected


def test_a_status_or_too_many_steps_ends_the_run():
    assert route({"topic": "x", "status": "published"}) == "end"
    assert route({"topic": "x", "steps": MAX_STEPS + 1}) == "end"
    assert route({"topic": "x", "steps": MAX_STEPS}) == "researcher"


def test_the_team_hands_work_on_in_order(tmp_path):
    client = team_client(
        research_reply(),
        notice_reply(),
        review_reply("revise", ["Too vague"]),
        notice_reply(),
        review_reply(),
    )
    app = build_team(
        client, tools={}, checkpointer=InMemorySaver(), outbox=str(tmp_path)
    )
    config = {"configurable": {"thread_id": "t1"}}
    app.invoke({"topic": "The Finance Portal outage this morning"}, config)
    state = app.get_state(config).values
    assert senders(state)[:5] == [
        "researcher",
        "writer",
        "reviewer",
        "writer",
        "reviewer",
    ]
    assert state["revisions"] == 1
    assert (
        "Too vague" in client.calls[3]["messages"][1]["content"]
    )  # the writer saw the reviewer's issue
    assert state["next"] == "human"
