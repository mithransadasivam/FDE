"""Day 8 homework: the document store's rules, as each person meets them through the tools. Run: python -m pytest -q tests/test_documents.py"""

import pytest

from app.integration import tools
from app.integration.models import ToolRefused
from bank import core
from tests.bankkit import bank, live_identity


@pytest.fixture(autouse=True)
def in_process_bank():
    tools.set_bank_http(bank())
    core.save("audit.json", [])  # the 20-an-hour limit counts the audit: start every test with no calls this hour
    yield
    tools.set_bank_http(None)


def test_each_person_sees_documents_within_their_remit():
    for who in ("tom.reyes", "grace.mensah", "helen.achebe"):
        docs = tools.list_documents(live_identity(who), "CU-022578")["documents"]  # a North 1 customer
        assert len(docs) == 1 and docs[0]["customer_id"] == "CU-022578"
    assert tools.get_document(live_identity("tom.reyes"), "DS-0001")["doc_id"] == "DS-0001"


def test_a_document_outside_the_remit_does_not_exist():
    for who in ("tom.reyes", "grace.mensah"):
        with pytest.raises(ToolRefused, match="No document DS-0075"):
            tools.get_document(live_identity(who), "DS-0075")
        with pytest.raises(ToolRefused, match="No customer CU-022478"):
            tools.list_documents(live_identity(who), "CU-022478")
    assert tools.get_document(live_identity("helen.achebe"), "DS-0075")["doc_id"] == "DS-0075"
    assert len(tools.list_documents(live_identity("helen.achebe"), "CU-022478")["documents"]) == 2


def test_the_audit_names_the_person_not_the_console():
    tools.get_document(live_identity("tom.reyes"), "DS-0001")
    with pytest.raises(ToolRefused):
        tools.get_document(live_identity("grace.mensah"), "DS-0075")
    entries = bank().get("/audit", params={"system": "documents", "limit": 10}).json()["entries"]
    seen = {(e["actor"], e["via"], e["outcome"]) for e in entries}
    assert ("tom.reyes", "fde-mcp", "allowed") in seen and ("grace.mensah", "fde-mcp", "refused") in seen
    assert not any(e["actor"].startswith("svc-") for e in entries)


def test_the_twenty_first_document_in_an_hour_is_refused():
    me = live_identity("tom.reyes")  # no other calls this hour: the fixture cleared the audit
    for _ in range(20):
        assert tools.get_document(me, "DS-0001")["doc_id"] == "DS-0001"
    with pytest.raises(ToolRefused, match="More than 20 documents"):
        tools.get_document(me, "DS-0001")
    assert tools.get_document(live_identity("grace.mensah"), "DS-0001")["doc_id"] == "DS-0001"  # the limit is per person
