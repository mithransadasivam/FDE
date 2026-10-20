"""Day 11 homework: tests for find_assets and assign_ticket. A temporary database and a fake model: no real calls."""

import json
import sqlite3

import pytest

import app.tool_loop as loop
from app.tool_loop import describe_action, run_tool, run_tool_loop
from app.tools import (
    ASSIGN_TICKET_SCHEMA,
    FIND_ASSETS_SCHEMA,
    TOOLS,
    assign_ticket,
    find_assets,
    get_ticket,
)
from tests.day11_fakes import FakeToolClient, asks, says, tiny_db, tool_call


def assets_db(path):
    """tiny_db plus an assets table with four devices."""
    db = tiny_db(path)
    with sqlite3.connect(db) as con:
        con.execute(
            """CREATE TABLE assets (asset_tag TEXT PRIMARY KEY, device_type TEXT, model TEXT,
               serial_number TEXT, assigned_to TEXT, department TEXT, purchase_date TEXT)"""
        )
        con.executemany(
            "INSERT INTO assets VALUES (?,?,?,?,?,?,?)",
            [
                ("IT-1", "laptop", "L14", "s1", "a.mensah", "Finance", "2023-03-14"),
                ("IT-2", "docking station", "D2", "s2", "a.mensah", "Finance", "2024-11-02"),
                ("IT-3", "laptop", "L14", "s3", "r.iyer", "HR", "2023-05-02"),
                ("IT-4", "monitor", "M24", "s4", "r.iyer", "HR", "2022-06-27"),
            ],
        )
    return db


@pytest.fixture
def actions(monkeypatch):
    """Capture the audit log instead of writing logs/actions.jsonl."""
    entries = []
    monkeypatch.setattr(loop, "log_action", lambda e: entries.append(e))
    return entries


# ------------------------------------------------------------ find_assets
def test_find_assets_by_user_department_and_type(tmp_path):
    db = assets_db(tmp_path / "t.db")
    mensah = find_assets(assigned_to="a.mensah", db_path=db)
    assert mensah["count"] == 2 and mensah["assets"][0]["purchase_date"] == "2023-03-14"
    assert find_assets(department="HR", db_path=db)["count"] == 2
    both = find_assets(department="HR", device_type="laptop", db_path=db)
    assert [a["asset_tag"] for a in both["assets"]] == ["IT-3"]
    assert find_assets(assigned_to="nobody.here", db_path=db) == {"count": 0, "assets": []}


def test_find_assets_without_a_filter_is_an_error(tmp_path):
    db = assets_db(tmp_path / "t.db")
    with pytest.raises(ValueError, match="at least one"):
        find_assets(db_path=db)
    assert "at least one" in run_tool("find_assets", "{}", db_path_tools(db))


def db_path_tools(db):
    """TOOLS where find_assets and assign_ticket use the temporary database."""
    from app.tools import Tool

    return {
        **TOOLS,
        "find_assets": Tool(
            lambda **a: find_assets(**a, db_path=db), FIND_ASSETS_SCHEMA
        ),
    }


def test_find_assets_values_are_parameters_and_the_connection_is_read_only(tmp_path):
    db = assets_db(tmp_path / "t.db")
    out = find_assets(department="HR'; DROP TABLE assets; --", db_path=db)
    assert out["count"] == 0  # treated as a value, not as SQL
    with sqlite3.connect(db) as con:
        assert con.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 4


def test_bad_find_assets_arguments_never_reach_the_tool(tmp_path):
    db = assets_db(tmp_path / "t.db")
    reached = []
    from app.tools import Tool

    tools = {
        "find_assets": Tool(lambda **a: reached.append(a) or {}, FIND_ASSETS_SCHEMA)
    }
    for bad in (
        {"device_type": "toaster"},
        {"assigned_to": "A.Mensah"},
        {"assigned_to": "a.mensah", "colour": "red"},
    ):
        assert "invalid arguments" in run_tool("find_assets", json.dumps(bad), tools)
    assert reached == []


def test_the_model_can_choose_find_assets(tmp_path):
    db = assets_db(tmp_path / "t.db")
    fake = FakeToolClient(
        asks(tool_call("find_assets", {"assigned_to": "a.mensah"})),
        says("a.mensah has a laptop and a docking station."),
    )
    out = run_tool_loop("Which devices does a.mensah have?", client=fake, tools=db_path_tools(db))
    assert [c["name"] for c in out["calls"]] == ["find_assets"]
    assert json.loads(out["calls"][0]["result"])["count"] == 2
    assert "find_assets" in [t["function"]["name"] for t in fake.calls[0]["tools"]]


# ------------------------------------------------------------ assign_ticket
def test_assign_ticket_gives_an_open_ticket_to_a_team(tmp_path):
    db = assets_db(tmp_path / "t.db")
    out = assign_ticket("INC-0001", "network team", db_path=db)
    assert out == {"id": "INC-0001", "old_assignee": "nobody", "new_assignee": "network team"}
    assert get_ticket("INC-0001", db_path=db)["assignee"] == "network team"


def test_assign_ticket_refuses_closed_and_unknown_tickets(tmp_path):
    db = assets_db(tmp_path / "t.db")
    with pytest.raises(ValueError, match="closed"):
        assign_ticket("INC-0003", "service desk", db_path=db)
    with pytest.raises(ValueError, match="no ticket"):
        assign_ticket("INC-9999", "service desk", db_path=db)
    assert get_ticket("INC-0003", db_path=db)["assignee"] == ""


def test_an_unknown_team_never_reaches_the_tool():
    reached = []
    from app.tools import Tool

    tools = {
        "assign_ticket": Tool(
            lambda **a: reached.append(a) or {}, ASSIGN_TICKET_SCHEMA, changes_data=True
        )
    }
    out = run_tool(
        "assign_ticket",
        json.dumps({"ticket_id": "INC-0001", "team": "marketing"}),
        tools,
        confirm=lambda s: True,
    )
    assert "invalid arguments" in out and "must be one of" in out and reached == []


def test_a_refusal_changes_nothing(tmp_path, actions):
    db = assets_db(tmp_path / "t.db")
    from app.tools import Tool

    tools = {
        "assign_ticket": Tool(
            lambda **a: assign_ticket(**a, db_path=db), ASSIGN_TICKET_SCHEMA, changes_data=True
        )
    }
    args = json.dumps({"ticket_id": "INC-0002", "team": "end-user team"})
    out = json.loads(run_tool("assign_ticket", args, tools, confirm=lambda s: False))
    assert out["done"] is False
    assert get_ticket("INC-0002", db_path=db)["assignee"] == ""
    assert actions[0]["approved"] is False and actions[0]["tool"] == "assign_ticket"
    # and an approval does change it, and is logged as approved
    out = json.loads(run_tool("assign_ticket", args, tools, confirm=lambda s: True))
    assert out["done"] is True and get_ticket("INC-0002", db_path=db)["assignee"] == "end-user team"
    assert actions[1]["approved"] is True


def test_the_approval_sentence_names_the_ticket_and_team():
    sentence = describe_action("assign_ticket", {"ticket_id": "INC-1013", "team": "end-user team"})
    assert sentence == "Give ticket INC-1013 to the end-user team"
    assert TOOLS["assign_ticket"].changes_data is True
    assert TOOLS["find_assets"].changes_data is False
