"""Ticket ENG-802: call the bank's systems as the person. Run: python -m pytest -q tests/test_downstream.py"""

import jwt
import pytest

from app.integration import tools
from app.integration.downstream import downstream_token
from app.integration.models import ToolRefused
from bank import core
from tests.bankkit import bank, live_identity


@pytest.fixture(autouse=True)
def in_process_bank():
    tools.set_bank_http(bank())
    yield
    tools.set_bank_http(None)


def test_the_token_is_a_new_one_for_the_crm_issued_to_tom_via_the_mcp_server():
    me = live_identity("tom.reyes")
    t = downstream_token(me, "crm", tools.bank_http())
    c = jwt.decode(t, options={"verify_signature": False})
    assert t != me.token and c["aud"] == "crm" and c["sub"] == "tom.reyes" and c["act"] == {"sub": "fde-mcp"}
    assert c["scope"] == "kyc.read kyc.write"


def test_tom_sees_his_team_and_the_audit_says_who_asked():
    assert tools.find_customer(live_identity("tom.reyes"))["total"] == 12
    last = bank().get("/audit", params={"system": "crm", "limit": 1}).json()["entries"][0]
    assert (last["actor"], last["via"]) == ("tom.reyes", "fde-mcp")


def test_each_person_their_remit():
    assert tools.find_customer(live_identity("grace.mensah"))["total"] == 24
    assert tools.find_customer(live_identity("helen.achebe"))["total"] == 72
    with pytest.raises(ToolRefused, match="No customer CU-022478"):
        tools.get_customer(live_identity("tom.reyes"), "CU-022478")


def test_the_banks_rules_apply_to_the_person():
    with pytest.raises(ToolRefused, match="read-only"):
        tools.add_customer_note(live_identity("helen.achebe"), "CU-022578", "test")
    with pytest.raises(ToolRefused, match="Only a team lead"):
        tools.assign_exception(live_identity("tom.reyes"), "KX-1001", "A01")
    assert tools.assign_exception(live_identity("grace.mensah"), "KX-1001", "A01")["assignee"] == "A01"


def test_a_note_is_written_in_the_persons_name():
    n = tools.add_customer_note(live_identity("tom.reyes"), "CU-022578", "Called the applicant")
    assert (n["by"], n["via"]) == ("tom.reyes", "fde-mcp")


def test_an_expired_token_cannot_be_exchanged():
    me = live_identity("tom.reyes")
    me.token = core.issue("tom.reyes", core.MCP_RESOURCE, ["kyc.read"], "test", now=1_700_000_000)
    with pytest.raises(ToolRefused, match="^The sign-in service refused the exchange: "):
        downstream_token(me, "crm", tools.bank_http())
