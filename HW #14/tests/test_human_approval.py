"""Activity 3: human_approval() pauses the team until a person decides. Run: pytest tests/test_human_approval.py"""

import sqlite3
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from app.team import build_team
from tests.day14_fakes import notice_reply, research_reply, review_reply, team_client

CONFIG = {"configurable": {"thread_id": "t1"}}


def paused_team(tmp_path, checkpointer=None, *extra):
    client = team_client(research_reply(), notice_reply(), review_reply(), *extra)
    app = build_team(
        client,
        tools={},
        checkpointer=checkpointer or InMemorySaver(),
        outbox=str(tmp_path),
    )
    result = app.invoke({"topic": "The Finance Portal outage this morning"}, CONFIG)
    return app, client, result


def test_the_team_pauses_and_shows_the_draft_and_review(tmp_path):
    app, _, result = paused_team(tmp_path)
    question = result["__interrupt__"][0].value
    assert question["question"] == "Publish this notice? approve, revise or reject"
    assert question["draft"]["title"] == "Finance Portal unavailable"
    assert question["review"]["verdict"] == "approve"
    assert app.get_state(CONFIG).next == ("human",)
    assert list(tmp_path.iterdir()) == []  # nothing published while waiting


def test_approve_publishes_the_notice(tmp_path):
    app, _, _ = paused_team(tmp_path)
    app.invoke(
        Command(resume={"decision": " Approve ", "comment": "OK to send"}), CONFIG
    )
    state = app.get_state(CONFIG).values
    assert state["status"] == "published"
    assert state["human"] == {"decision": "approve", "comment": "OK to send"}
    text = Path(state["published_to"]).read_text(encoding="utf-8")
    assert text.startswith("# Finance Portal unavailable") and "OK to send" in text


def test_revise_sends_the_comment_back_to_the_writer(tmp_path):
    app, client, _ = paused_team(
        tmp_path,
        None,
        notice_reply(title="Finance Portal down: next update 11:00"),
        review_reply(),
    )
    result = app.invoke(
        Command(
            resume={"decision": "revise", "comment": "Say when the next update is"}
        ),
        CONFIG,
    )
    assert (
        "From the person approving: Say when the next update is"
        in client.calls[3]["messages"][1]["content"]
    )
    assert (
        result["__interrupt__"][0].value["draft"]["title"]
        == "Finance Portal down: next update 11:00"
    )


def test_reject_and_unclear_answers_publish_nothing(tmp_path):
    for i, answer in enumerate(
        [
            {"decision": "reject", "comment": "Not needed"},
            {"decision": "yes please"},
            "ok",
        ]
    ):
        app, _, _ = paused_team(tmp_path)
        config = {"configurable": {"thread_id": "t1"}}
        app.invoke(Command(resume=answer), config)
        state = app.get_state(config).values
        assert state["status"] == "rejected", i
        assert state["human"]["decision"] == "reject"
    assert list(tmp_path.iterdir()) == []


def test_a_saved_checkpoint_lets_a_new_process_resume(tmp_path):
    db = tmp_path / "checkpoints.db"
    with sqlite3.connect(db, check_same_thread=False) as con:
        paused_team(tmp_path / "out", SqliteSaver(con))
    with sqlite3.connect(
        db, check_same_thread=False
    ) as con:  # later, a new team object
        app = build_team(
            team_client(review_reply()),
            tools={},
            checkpointer=SqliteSaver(con),
            outbox=str(tmp_path / "out"),
        )
        assert (
            app.get_state(CONFIG).values["draft"]["title"]
            == "Finance Portal unavailable"
        )
        app.invoke(Command(resume={"decision": "approve", "comment": ""}), CONFIG)
        assert app.get_state(CONFIG).values["status"] == "published"
