"""Phase 5 checkpoint: an in-process client lists tools, resources and the prompt; a query for an account number is
refused and logged; create_vendor is absent with writes off."""
import asyncio
import json

import pytest
from mcp import Client

from vendor_desk import config
from vendor_desk.mcp_server import build_server

READ_ONLY = {"read_request", "get_vendor", "find_vendor", "screen_watchlist", "check_documents", "check_payment_terms",
             "check_bank_country", "check_spend_threshold", "lookup_policy", "query_vendor_db"}


def with_client(server, work):
    async def main():
        async with Client(server) as client:
            return await work(client)
    return asyncio.run(main())


def call(server, name, args):
    return with_client(server, lambda c: c.call_tool(name, args))


def log_lines():
    p = config.query_log_path()
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()] if p.exists() else []


def test_tools_resources_and_prompt_are_listed(db):
    server = build_server(db_path=db, allow_writes=False)

    async def work(c):
        return (await c.list_tools(), await c.list_resources(), await c.list_resource_templates(),
                await c.list_prompts())

    tools, resources, templates, prompts = with_client(server, work)
    assert {t.name for t in tools.tools} == READ_ONLY
    assert all(t.annotations and t.annotations.read_only_hint for t in tools.tools)
    assert "procurement://policy" in {str(r.uri) for r in resources.resources}
    assert any("vendors/{vendor_id}" in t.uri_template for t in templates.resource_templates)
    assert [p.name for p in prompts.prompts] == ["assess_request"]


def test_create_vendor_is_not_listed_when_writes_are_off(db):
    server = build_server(db_path=db, allow_writes=False)
    names = {t.name for t in with_client(server, lambda c: c.list_tools()).tools}
    assert "create_vendor" not in names
    on = build_server(db_path=db, allow_writes=True)
    assert "create_vendor" in {t.name for t in with_client(on, lambda c: c.list_tools()).tools}


def test_writes_default_to_off(db, monkeypatch):
    monkeypatch.delenv("VENDOR_WRITES", raising=False)
    names = {t.name for t in with_client(build_server(db_path=db), lambda c: c.list_tools()).tools}
    assert "create_vendor" not in names


def test_tool_call_returns_data_and_is_logged(db):
    server = build_server(db_path=db, allow_writes=False)
    r = call(server, "check_payment_terms", {"days": 60})
    data = json.loads(r.content[0].text)
    assert not r.is_error and data["result"] == "fail" and data["policy_section"] == "§5.1"
    assert log_lines()[-1]["tool"] == "check_payment_terms" and log_lines()[-1]["outcome"] == "ok"


def test_a_query_for_an_account_number_is_refused_and_the_refusal_is_logged(db):
    server = build_server(db_path=db, allow_writes=False)
    r = call(server, "query_vendor_db", {"sql": "SELECT account_number FROM bank_accounts"})
    assert r.is_error and "private" in r.content[0].text.lower()
    assert "99310442" not in r.content[0].text
    last = log_lines()[-1]
    assert last["tool"] == "query_vendor_db" and last["outcome"] == "refused"
    # a harmless query still works, and the log never holds an account number
    ok = call(server, "query_vendor_db", {"sql": "SELECT name FROM vendors WHERE payment_terms_days = 60"})
    assert not ok.is_error and "Brightpath" in ok.content[0].text
    assert "99310442" not in config.query_log_path().read_text(encoding="utf-8")


def test_bad_arguments_are_errors_not_crashes(db):
    server = build_server(db_path=db, allow_writes=False)
    assert call(server, "read_request", {"request_id": "banana"}).is_error
    r = call(server, "read_request", {"request_id": "REQ-999"})
    assert r.is_error and "no request file" in r.content[0].text
    assert call(server, "check_payment_terms", {"days": 9999}).is_error


def test_resources_policy_and_vendor(db):
    server = build_server(db_path=db, allow_writes=False)
    policy = with_client(server, lambda c: c.read_resource("procurement://policy"))
    assert "§3.2" in policy.contents[0].text
    vendor = with_client(server, lambda c: c.read_resource("procurement://vendors/VEN-1010"))
    text = vendor.contents[0].text
    assert "Brightpath Software Ltd" in text and "60 days" in text and "99809326" not in text
    with pytest.raises(Exception):
        with_client(server, lambda c: c.read_resource("procurement://vendors/VEN-9999"))


def test_the_prompt_tells_a_host_how_to_assess_a_case(db):
    server = build_server(db_path=db, allow_writes=False)
    r = with_client(server, lambda c: c.get_prompt("assess_request", {"case_id": "VOB-007"}))
    text = r.messages[0].content.text
    assert "REQ-007" in text and "check_documents" in text and "screen_watchlist" in text and "§7" in text


def test_create_vendor_refuses_too_few_approvers_and_is_idempotent(db):
    server = build_server(db_path=db, allow_writes=True)
    args = {"case_id": "VOB-009", "request_ids": ["REQ-009"], "approvers": ["a@example.com"],
            "approvals_required": 2, "payment_terms_days": 30}
    r = call(server, "create_vendor", args)
    assert r.is_error and "needs 2" in r.content[0].text
    ok = {**args, "approvers": ["a@example.com", "b@example.com"]}
    first = json.loads(call(server, "create_vendor", ok).content[0].text)
    second = json.loads(call(server, "create_vendor", ok).content[0].text)
    assert first["created"] and not second["created"] and first["vendor_id"] == second["vendor_id"]
    count = json.loads(call(server, "query_vendor_db", {"sql": "SELECT COUNT(*) FROM vendors"}).content[0].text)
    assert count["rows"] == [[21]]


def test_calls_rejected_by_the_schema_are_logged_too(db):
    server = build_server(db_path=db, allow_writes=False)
    assert call(server, "check_payment_terms", {"days": 9999}).is_error
    assert call(server, "nonexistent_tool", {}).is_error
    outcomes = [(l["tool"], l["outcome"]) for l in log_lines()]
    assert ("check_payment_terms", "invalid") in outcomes and ("nonexistent_tool", "invalid") in outcomes
