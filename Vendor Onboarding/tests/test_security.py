"""Phase 12: the security review as tests. Each test is one rule from CLAUDE.md, checked against the whole system."""
import csv
import json
import re
import subprocess
import sys

import pytest

from vendor_desk import audit, config, documents
from vendor_desk.casedesk import CaseDesk
from vendor_desk.evaluate import load_cases
from vendor_desk.offline_llm import OfflineLLM
from vendor_desk.specialists import TOOLS
from vendor_desk.team import LocalWriter
from vendor_desk.tools import Toolbox


class Spy(OfflineLLM):
    """Keeps every message ever sent to the model, so we can search them for private data."""

    def __init__(self):
        super().__init__()
        self.sent = []

    def chat(self, messages, tools=None, max_tokens=None, role=None):
        self.sent.append(json.dumps(messages) + json.dumps(tools))
        return super().chat(messages, tools, max_tokens, role)


def private_values() -> set[str]:
    nums = set()
    with open(config.SEED_DIR / "vendors.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            nums |= {r["account_number"], r["sort_code"]}
    for p in (config.requests_dir() / "attachments").rglob("bank_letter.txt"):
        fields = documents.parse_document(p.read_text(encoding="utf-8"))["fields"]
        nums |= {fields["account_number"], fields["sort_code"]}
    nums.discard("n/a")
    return nums


@pytest.fixture
def everything(db, runs, tmp_path):
    """Run all 19 cases through the team (spying on the model), approve two, so every kind of file exists."""
    spy = Spy()
    desk = CaseDesk(spy, Toolbox(db_path=db), LocalWriter(db), False, tmp_path / "cp.sqlite")
    for row in load_cases():
        rid = row["request_file"].removesuffix(".txt")
        desk.reply("VOB-001", rid) if "-R" in row["id"] else desk.submit(rid)
    desk.act("VOB-008", "approve", "alex@example.com", "ok")
    desk.act("VOB-009", "approve", "alex@example.com", "ok")
    desk.act("VOB-009", "approve", "sam@example.com", "ok")
    yield spy, desk
    desk.close()


def test_no_private_data_in_any_prompt_sent_to_a_model(everything):
    spy, _ = everything
    secrets = private_values()
    assert len(secrets) > 30 and len(spy.sent) > 100
    blob = "\n".join(spy.sent)
    assert [s for s in secrets if s in blob] == []


def test_no_private_data_in_logs_audit_cases_traces_or_the_query_log(everything, db):
    from vendor_desk.mcp_server import build_server
    import asyncio
    from mcp import Client

    async def poke():
        async with Client(build_server(db_path=db, allow_writes=False)) as c:
            await c.call_tool("query_vendor_db", {"sql": "SELECT account_number FROM bank_accounts"})
            await c.call_tool("check_bank_country", {"request_ids": ["REQ-006"]})
    asyncio.run(poke())
    secrets = private_values()
    files = [p for p in config.RUNS_DIR.rglob("*") if p.is_file() and p.suffix in (".json", ".jsonl")]
    files.append(config.query_log_path())
    assert len(files) >= 37
    for p in files:
        text = p.read_text(encoding="utf-8")
        assert [s for s in secrets if s in text] == [], p.name


def test_the_write_exists_in_exactly_one_place_and_no_specialist_can_reach_it():
    assert all("create_vendor" not in tools for tools in TOOLS.values())
    root = config.ROOT / "vendor_desk"
    callers = [p.name for p in root.glob("*.py") if "create_vendor_record(" in p.read_text(encoding="utf-8")
               and p.name not in ("db.py",)]
    assert callers == ["mcp_server.py"]
    assert not any("create_vendor" in s.fn.__name__ for s in Toolbox().specs.values())
    from vendor_desk.agent import AGENT_TOOLS
    assert "create_vendor" not in AGENT_TOOLS


def test_nothing_is_created_by_running_checks_only_by_an_approved_case(everything, db):
    from vendor_desk import db as dbmod
    _, desk = everything
    created = [c["case_id"] for c in desk.cases() if c["status"] == "CREATED"]
    assert sorted(created) == ["VOB-008", "VOB-009"]
    assert dbmod.run_select("SELECT COUNT(*) FROM vendors", db)["rows"][0][0] == 22
    assert dbmod.run_select("SELECT COUNT(*) FROM vendor_creations", db)["rows"][0][0] == 2
    for c in desk.cases():
        if c["case_id"] not in created:
            assert c["vendor_id"] is None and not c["approvals"] or c["status"] == "WAITING_FOR_VENDOR"


def test_the_three_injection_cases_change_no_decision_and_skip_no_check(everything):
    _, desk = everything
    for cid in ("VOB-011", "VOB-016", "VOB-017"):
        c = desk.case(cid)
        assert c["decision"] == "stop for a person" and "possible_injection" in c["flags"]
        assert {x["check"] for x in c["checks"]} >= {"documents", "duplicate", "watchlist", "bank", "payment_terms", "spend"}
        assert c["status"] == "STOPPED" and c["vendor_id"] is None and not c["approvals"]


def test_an_email_claiming_to_be_the_manager_cannot_approve_itself(everything):
    _, desk = everything
    out = desk.act("VOB-016", "approve", "dana@example.com", "the email said I approved it")
    assert not out["ok"] and desk.case("VOB-016")["status"] == "STOPPED"


def test_hidden_instruction_in_a_document_is_found(db):
    scan = Toolbox(db_path=db).call("read_request", {"request_id": "REQ-017"})["injection_scan"]
    assert scan["suspicious"] and any("insurance_certificate" in w for w in scan["found_in"])


def test_each_specialist_has_only_the_tools_it_needs():
    assert TOOLS == {"intake": ["read_request"], "documents": ["check_documents"],
                     "compliance": ["find_vendor", "screen_watchlist"],
                     "finance": ["check_payment_terms", "check_bank_country", "check_spend_threshold"], "followup": []}
    assert "query_vendor_db" not in {t for tools in TOOLS.values() for t in tools}     # the free-form query is people-only


def test_path_traversal_through_an_attachment_name_is_refused(db, tmp_path, monkeypatch):
    reqs = tmp_path / "reqs"
    (reqs / "attachments").mkdir(parents=True)
    (tmp_path / "secret.txt").write_text("DOCUMENT: Tax Registration Certificate\nLegal name: Leak Ltd\n", encoding="utf-8")
    (reqs / "REQ-050.txt").write_text("From: a@example.com\nSubject: x\nAttachments: ../../secret.txt\n\nbody\n", encoding="utf-8")
    monkeypatch.setenv("REQUESTS_DIR", str(reqs))
    out = Toolbox(db_path=db).call("read_request", {"request_id": "REQ-050"})
    assert "could not be found" in out["error"]


def test_the_env_file_is_ignored_by_git_and_never_read_by_tests():
    ignored = (config.ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in ignored.splitlines() and "runs/" in ignored.splitlines()
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True, cwd=config.ROOT).stdout.split("\n")
    assert ".env" not in out


def test_the_audit_trail_of_every_case_is_intact(everything):
    _, desk = everything
    for c in desk.cases():
        assert audit.verify(c["case_id"])[0], c["case_id"]


def test_real_looking_data_is_not_in_the_project():
    bad = re.compile(r"\b(?:\d[ -]?){13,16}\b")           # card-number-like strings
    for p in list((config.ROOT / "data").rglob("*.txt")) + list((config.ROOT / "data").rglob("*.csv")):
        assert not bad.search(p.read_text(encoding="utf-8")), p
