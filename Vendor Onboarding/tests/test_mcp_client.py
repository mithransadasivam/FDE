"""Phase 7 checkpoint: the agent gets its tools from the MCP server (a real child process), gives the same decisions as
with local tools, and with the server stopped a case ends with a clear status and no decision. Fake models only."""
import pytest

from vendor_desk import review
from vendor_desk.agent import run_agent
from vendor_desk.backends import make_backend
from vendor_desk.evaluate import run_part1, summarise
from vendor_desk.llm import ScriptedLLM, calls
from vendor_desk.mcp_client import McpBackend
from vendor_desk.offline_llm import OfflineLLM
from vendor_desk.tools import BackendDown, Toolbox


@pytest.fixture
def mcp(db):
    backend = McpBackend()
    yield backend
    backend.close()


def test_the_client_lists_the_servers_tools_and_converts_them_for_the_agent(mcp):
    names = set(mcp.tool_names())
    assert {"read_request", "find_vendor", "check_documents"} <= names and "create_vendor" not in names
    spec = mcp.openai_tools(["find_vendor"])[0]["function"]
    assert spec["name"] == "find_vendor" and "duplicate" in spec["description"].lower() or "vendor master" in spec["description"]
    assert spec["parameters"]["properties"]["name"]["type"] == "string"


def test_calls_return_the_same_result_as_the_local_tools(db, mcp):
    local = Toolbox(db_path=db)
    for name, args in [("check_documents", {"request_ids": ["REQ-007"]}), ("screen_watchlist", {"name": "Veltrax Marine Supply Ltd"}),
                       ("check_bank_country", {"request_ids": ["REQ-006"]}), ("check_spend_threshold", {"amount_gbp": 2100, "period": "month"})]:
        assert mcp.call(name, args) == local.call(name, args)


def test_server_errors_come_back_as_readable_errors(mcp):
    assert "no request file" in mcp.call("read_request", {"request_id": "REQ-999"})["error"]
    assert "private" in mcp.call("query_vendor_db", {"sql": "SELECT account_number FROM bank_accounts"})["error"].lower()


def test_all_cases_give_the_same_decisions_with_mcp_tools_as_with_local_tools(db, mcp, runs):
    local = run_part1(OfflineLLM(), Toolbox(db_path=db), engine="local", progress=lambda *_: None)
    via_mcp = run_part1(OfflineLLM(), mcp, engine="mcp", progress=lambda *_: None)
    assert [s.got for s in local["scores"]] == [s.got for s in via_mcp["scores"]]
    assert [s.flags for s in local["scores"]] == [s.flags for s in via_mcp["scores"]]
    t = summarise(via_mcp["scores"])
    assert t["decisions_right"] == 19 and t["problems"] == 0


def test_server_down_at_the_start_ends_with_a_clear_status_and_no_decision(db):
    dead = McpBackend(command="python-that-does-not-exist-xyz")
    run = run_agent("REQ-002", OfflineLLM(), dead, case_id="VOB-002")
    assert run.status == "backend_down" and run.assessment is None
    assert "not reachable" in run.message or "not start" in run.message
    assert any(p["code"] == "backend_down" for p in review.review_run(run))


def test_server_stopped_in_the_middle_of_a_case_ends_with_no_decision(db):
    backend = McpBackend(timeout=10)
    llm = ScriptedLLM(calls(("read_request", {"request_id": "REQ-002"})), calls(("check_documents", {"request_ids": ["REQ-002"]})))
    assert backend.tool_names()
    # stop the server process after the first call, as if it crashed
    orig_call = backend.call
    state = {"n": 0}

    def call_then_kill(name, args):
        out = orig_call(name, args)
        state["n"] += 1
        if state["n"] == 1:
            backend.close()
        return out
    backend.call = call_then_kill
    run = run_agent("REQ-002", llm, backend)
    assert run.status == "backend_down" and run.assessment is None


def test_make_backend_switch(db, monkeypatch):
    assert isinstance(make_backend("local"), Toolbox)
    monkeypatch.setenv("TOOLS_BACKEND", "mcp")
    assert isinstance(make_backend(), McpBackend)
