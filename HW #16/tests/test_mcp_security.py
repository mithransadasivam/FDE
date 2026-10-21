"""Activity 4: authorize() hides personal data and refuses anything but reading.
Run: pytest tests/test_mcp_security.py"""

import sqlite3

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from app.mcp_server import authorize, build_server, run_query
from tests.day13_helpers import call_tool, with_client


def test_reading_a_hidden_column_is_denied_and_others_allowed():
    assert (
        authorize(sqlite3.SQLITE_READ, "staff", "home_address", "main", None)
        == sqlite3.SQLITE_DENY
    )
    assert (
        authorize(sqlite3.SQLITE_READ, "staff", "date_of_birth", "main", None)
        == sqlite3.SQLITE_DENY
    )
    assert (
        authorize(sqlite3.SQLITE_READ, "staff", "full_name", "main", None)
        == sqlite3.SQLITE_OK
    )
    assert (
        authorize(sqlite3.SQLITE_READ, "tickets", "status", "main", None)
        == sqlite3.SQLITE_OK
    )
    assert authorize(sqlite3.SQLITE_SELECT, None, None, None, None) == sqlite3.SQLITE_OK
    assert (
        authorize(sqlite3.SQLITE_FUNCTION, None, "count", None, None)
        == sqlite3.SQLITE_OK
    )


@pytest.mark.parametrize(
    "action",
    [
        sqlite3.SQLITE_INSERT,
        sqlite3.SQLITE_UPDATE,
        sqlite3.SQLITE_DELETE,
        sqlite3.SQLITE_PRAGMA,
        sqlite3.SQLITE_ATTACH,
    ],
)
def test_anything_but_reading_is_denied(action):
    assert authorize(action, "tickets", None, "main", None) == sqlite3.SQLITE_DENY


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM staff WHERE username = 't.sato'",
        "SELECT full_name, home_address FROM staff",
        "SELECT username FROM staff WHERE date_of_birth LIKE '199%'",
        "SELECT t.id FROM tickets t JOIN staff s ON s.username = t.requester ORDER BY s.personal_mobile",
    ],
)
def test_queries_that_touch_personal_data_fail(db, sql):
    with pytest.raises(ToolError) as e:
        run_query(sql, db)
    assert "prohibited" in str(e.value)


def test_ordinary_staff_questions_still_work(db):
    out = run_query(
        "SELECT full_name, job_title, work_email FROM staff WHERE username = 't.sato'",
        db,
    )
    assert out["rows"] == [
        ["Takeshi Sato", "Engineering Manager", "t.sato@example.com"]
    ]
    joined = run_query(
        "SELECT s.department, COUNT(*) FROM tickets t JOIN staff s ON s.username = t.requester "
        "WHERE t.status = 'open' GROUP BY s.department ORDER BY 2 DESC, 1 LIMIT 1",
        db,
    )
    assert joined["row_count"] == 1


def test_read_only_is_the_default_and_writes_must_be_switched_on(db):
    names = with_client(build_server(db), lambda c: c.list_tools())
    assert sorted(t.name for t in names.tools) == ["describe_database", "run_query"]
    assert all(t.annotations.read_only_hint for t in names.tools)
    writable = build_server(db, allow_writes=True)
    result = call_tool(
        writable,
        "update_ticket_status",
        {"ticket_id": "INC-1013", "status": "in_progress", "note": "Looking"},
    )
    assert result.is_error is False
    assert run_query("SELECT status FROM tickets WHERE id = 'INC-1013'", db)[
        "rows"
    ] == [["in_progress"]]
