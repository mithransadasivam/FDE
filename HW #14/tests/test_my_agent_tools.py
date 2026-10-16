"""Day 12 homework: tests for device_age and the agent's tool list. A temporary database: no real calls."""

import json
import sqlite3

import pytest

from app.memory import NoteBook
from app.research_tools import DEVICE_AGE_SCHEMA, agent_tools, device_age
from app.tool_loop import run_tool


def assets_db(path):
    db = str(path / "h.db")
    with sqlite3.connect(db) as con:
        con.execute(
            """CREATE TABLE assets (asset_tag TEXT PRIMARY KEY, device_type TEXT, model TEXT,
               serial_number TEXT, assigned_to TEXT, department TEXT, purchase_date TEXT)"""
        )
        con.executemany(
            "INSERT INTO assets VALUES (?,?,?,?,?,?,?)",
            [
                ("IT-004512", "laptop", "L14", "s1", "a.mensah", "Finance", "2023-03-14"),
                ("IT-003977", "laptop", "L14", "s2", "t.sato", "Engineering", "2021-09-08"),
            ],
        )
    return db


def test_device_age_returns_the_purchase_date_and_age_in_years(tmp_path):
    r = device_age("IT-003977", today="2026-10-13", db_path=assets_db(tmp_path))
    assert r["purchase_date"] == "2021-09-08" and r["age_years"] == 5.1
    assert r["assigned_to"] == "t.sato"


def test_device_age_does_not_apply_any_replacement_rule(tmp_path):
    r = device_age("IT-003977", today="2026-10-13", db_path=assets_db(tmp_path))
    assert not {"due", "overdue", "replace", "replacement"} & {k.lower() for k in r}


def test_device_age_unknown_tag_raises_a_helpful_error(tmp_path):
    with pytest.raises(ValueError, match="find_assets"):
        device_age("IT-999999", db_path=assets_db(tmp_path))


def test_the_schema_rejects_bad_tags_and_points_to_the_other_tools():
    out = run_tool("device_age", json.dumps({"asset_tag": "laptop"}), agent_tools(NoteBook()))
    assert "invalid arguments" in out
    d = DEVICE_AGE_SCHEMA["description"]
    assert "find_assets" in d and "search_policies" in d and "does not apply" in d


def test_the_agent_has_device_age_and_find_assets_and_still_cannot_change_data(tmp_path):
    tools = agent_tools(NoteBook())
    assert {"device_age", "find_assets"} <= set(tools)
    assert not any(t.changes_data for t in tools.values())
    db = assets_db(tmp_path)
    with pytest.raises(sqlite3.OperationalError):  # the connection is read-only
        from app.tools import _read_only

        with _read_only(db) as con:
            con.execute("UPDATE assets SET model = 'x'")
