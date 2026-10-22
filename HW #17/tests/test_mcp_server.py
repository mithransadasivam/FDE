"""Activity 1: run_query() runs one read-only SELECT for the AI. Run: pytest tests/test_mcp_server.py"""

import json

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from app.mcp_server import MAX_ROWS, build_server, run_query
from tests.day13_helpers import call_tool


def test_select_returns_columns_and_rows(db):
    out = run_query("SELECT id, status FROM tickets WHERE id = 'INC-1001'", db)
    assert out == {
        "columns": ["id", "status"],
        "rows": [["INC-1001", "closed"]],
        "row_count": 1,
        "truncated": False,
    }


def test_trailing_semicolon_spaces_and_lower_case_are_fine(db):
    out = run_query("  select count(*) as n from tickets where status = 'open' ;  ", db)
    assert out["columns"] == ["n"] and out["rows"] == [[23]]


def test_large_results_are_cut_to_max_rows(db):
    out = run_query("SELECT a.id, b.id FROM tickets a, tickets b", db)  # 1,600 rows
    assert out["row_count"] == MAX_ROWS == len(out["rows"])
    assert out["truncated"] is True


@pytest.mark.parametrize(
    "sql, message",
    [
        ("DELETE FROM tickets", "Only one SELECT query is allowed."),
        ("", "Only one SELECT query is allowed."),
        ("SELECT 1; DROP TABLE tickets", "Send one query at a time, without ';'."),
        ("SELECT colour FROM tickets", "The query failed: no such column: colour"),
    ],
)
def test_problems_raise_tool_error_with_a_clear_message(db, sql, message):
    with pytest.raises(ToolError) as e:
        run_query(sql, db)
    assert str(e.value) == message


def test_the_server_offers_run_query_to_a_client(db):
    result = call_tool(
        build_server(db),
        "run_query",
        {"sql": "SELECT asset_tag FROM assets WHERE assigned_to = 't.sato'"},
    )
    assert result.is_error is False
    data = json.loads(result.content[0].text)
    assert sorted(r[0] for r in data["rows"]) == ["IT-003977", "IT-006210"]
