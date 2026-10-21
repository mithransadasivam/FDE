"""Day 11, Activity 4: no change to data without the user's approval, and every decision logged."""

import json

import app.tool_loop as loop
from app.tool_loop import approve_and_run, run_tool
from app.tools import UPDATE_TICKET_SCHEMA, Tool

ARGS = {
    "ticket_id": "INC-1017",
    "status": "closed",
    "note": "User confirmed VPN works again",
}


def make_tool():
    ran = []
    return Tool(
        lambda **a: ran.append(a) or {"id": a["ticket_id"], "new_status": a["status"]},
        UPDATE_TICKET_SCHEMA,
        changes_data=True,
    ), ran


def logged(monkeypatch):
    entries = []
    monkeypatch.setattr(loop, "log_action", lambda e: entries.append(e))
    return entries


def test_without_a_confirm_function_nothing_changes(monkeypatch):
    entries = logged(monkeypatch)
    tool, ran = make_tool()
    out = approve_and_run("update_ticket", tool, ARGS, confirm=None)
    assert out["done"] is False and "nothing was changed" in out["message"]
    assert ran == [] and entries == [
        {"tool": "update_ticket", "arguments": ARGS, "approved": False}
    ]


def test_a_refusal_changes_nothing(monkeypatch):
    entries = logged(monkeypatch)
    tool, ran = make_tool()
    out = approve_and_run("update_ticket", tool, ARGS, confirm=lambda s: False)
    assert out["done"] is False and ran == [] and entries[0]["approved"] is False


def test_only_a_real_true_counts_as_approval(monkeypatch):
    logged(monkeypatch)
    tool, ran = make_tool()
    approve_and_run(
        "update_ticket", tool, ARGS, confirm=lambda s: "yes"
    )  # a string is not approval
    assert ran == []


def test_approval_runs_the_tool_once_and_logs_it(monkeypatch):
    entries = logged(monkeypatch)
    tool, ran = make_tool()
    seen = []
    out = approve_and_run(
        "update_ticket", tool, ARGS, confirm=lambda s: seen.append(s) or True
    )
    assert out == {"done": True, "id": "INC-1017", "new_status": "closed"}
    assert ran == [ARGS] and entries == [
        {"tool": "update_ticket", "arguments": ARGS, "approved": True}
    ]
    assert "INC-1017" in seen[0] and "closed" in seen[0]


def test_read_only_tools_never_ask_and_write_tools_always_do(monkeypatch):
    logged(monkeypatch)
    tool, ran = make_tool()
    asked = []
    tools = {
        "update_ticket": tool,
        "read": Tool(
            lambda: {"ok": True}, {"name": "read", "parameters": {"type": "object"}}
        ),
    }
    assert json.loads(
        run_tool("read", "{}", tools, confirm=lambda s: asked.append(s) or True)
    ) == {"ok": True}
    assert asked == []
    run_tool(
        "update_ticket",
        json.dumps(ARGS),
        tools,
        confirm=lambda s: asked.append(s) or True,
    )
    assert len(asked) == 1 and len(ran) == 1
