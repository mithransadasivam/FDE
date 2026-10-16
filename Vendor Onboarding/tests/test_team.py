"""Phases 8 and 10: the team (supervisor, specialists, reviewer), the approval gate and the one write. Fake models only."""
import json
from contextlib import closing
from datetime import datetime, timedelta, timezone

import pytest

from vendor_desk import audit, casestore, config, db as dbmod
from vendor_desk.casedesk import CaseDesk
from vendor_desk.evaluate import load_cases, split
from vendor_desk.offline_llm import OfflineLLM
from vendor_desk.states import State
from vendor_desk.team import LocalWriter, route
from vendor_desk.tools import Toolbox


class RecordingLLM(OfflineLLM):
    """OfflineLLM that remembers which tools each role was offered."""

    def __init__(self, faults=None):
        super().__init__(faults)
        self.offered = {}

    def chat(self, messages, tools=None, max_tokens=None, role=None):
        r = super().chat(messages, tools, max_tokens, role)
        name = self.calls[-1]
        self.offered.setdefault(name, set()).update(t["function"]["name"] for t in tools or [])
        return r


def make_desk(db, tmp_path, llm=None, backend=None, parallel=False, name="cp.sqlite"):
    return CaseDesk(llm or OfflineLLM(), backend or Toolbox(db_path=db), LocalWriter(db), parallel, tmp_path / name)


@pytest.fixture
def desk(db, runs, tmp_path):
    d = make_desk(db, tmp_path)
    yield d
    d.close()


def vendor_count(db):
    return dbmod.run_select("SELECT COUNT(*) FROM vendors", db)["rows"][0][0]


# ------------------------------------------------------------------ Phase 8
def test_a_run_prints_each_handoff_in_order(desk):
    lines = []
    desk.submit("REQ-002", on_event=lines.append)
    order = [l.split(":")[0].split(" ")[0] for l in lines if "-> supervisor:" in l and not l.startswith("supervisor")]
    assert order == ["intake", "documents", "finance", "compliance", "reviewer"]
    assert any(l.startswith("finalize") for l in lines) and any("waiting for a person" in l for l in lines)


def test_every_specialist_gets_only_its_own_tools(db, runs, tmp_path):
    llm = RecordingLLM()
    d = make_desk(db, tmp_path, llm)
    d.submit("REQ-001")
    d.close()
    assert llm.offered["intake"] == {"read_request", "submit_report"}
    assert llm.offered["documents"] == {"check_documents", "submit_report"}
    assert llm.offered["compliance"] == {"find_vendor", "screen_watchlist", "submit_report"}
    assert llm.offered["finance"] == {"check_payment_terms", "check_bank_country", "check_spend_threshold", "submit_report"}
    assert llm.offered["followup"] == {"submit_report"}          # the writer has no tools at all
    assert "create_vendor" not in set().union(*llm.offered.values())


def test_a_bad_handoff_is_retried_once_with_the_error(db, runs, tmp_path):
    d = make_desk(db, tmp_path, OfflineLLM(faults={"finance": "invalid"}))
    lines = []
    case = d.submit("REQ-002", on_event=lines.append)
    d.close()
    assert case["status"] == "READY_FOR_APPROVAL"
    assert any("rejected at the boundary, retried once" in l for l in lines)
    assert any(e["event"] == "handoff_rejected" for e in audit.read("VOB-002"))


def test_a_handoff_that_fails_twice_stops_the_case(db, runs, tmp_path):
    d = make_desk(db, tmp_path, OfflineLLM(faults={"documents": "always_invalid"}))
    case = d.submit("REQ-002")
    d.close()
    assert case["status"] == "STOPPED" and "documents specialist stopped" in case["stop_reason"]
    assert case["decision"] is None and vendor_count(db) == 20


def test_the_reviewer_sends_work_back_and_the_case_still_ends_right(db, runs, tmp_path):
    d = make_desk(db, tmp_path, OfflineLLM(faults={"compliance": "wrong"}))
    lines = []
    case = d.submit("REQ-004", on_event=lines.append)
    d.close()
    assert any("SENT BACK to compliance" in l for l in lines)
    assert case["decision"] == "stop for a person" and "watchlist_near_match" in case["flags"]
    assert case["reviewer"]["revisions"] == 1


def test_the_revision_limit_stops_a_reviewer_that_is_never_satisfied(db, runs, tmp_path):
    d = make_desk(db, tmp_path, OfflineLLM(faults={"compliance": "always_wrong"}))
    case = d.submit("REQ-004")
    d.close()
    assert case["status"] == "STOPPED" and "Revision limit" in case["stop_reason"]


def test_the_supervisor_step_limit_stops_the_case(db, runs, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SUPERVISOR_STEP_LIMIT", 2)
    d = make_desk(db, tmp_path)
    case = d.submit("REQ-002")
    d.close()
    assert case["status"] == "STOPPED" and "Supervisor step limit" in case["stop_reason"]


def test_routing_is_a_short_rule():
    base = {"request": {"x": 1}, "documents": {}, "finance": {}, "compliance": {}, "review": None}
    assert route({}) == ["intake"]
    assert route({"request": {"x": 1}}) == ["documents"] and route({"request": {"x": 1}}, parallel=True) == ["documents", "finance"]
    assert route({**base, "compliance": None}) == ["compliance"]
    assert route(base) == ["reviewer"]
    assert route({**base, "review": {"verdict": "approve", "decision": "waiting for vendor"}, "followup": None}) == ["followup"]
    assert route({**base, "review": {"verdict": "approve", "decision": "ready for approval"}}) == ["finalize"]
    assert route({**base, "stop_reason": "x"}) == ["finalize"]


def test_parallel_mode_gives_the_same_decisions(db, runs, tmp_path):
    seq = make_desk(db, tmp_path, name="a.sqlite")
    par = make_desk(db, tmp_path, parallel=True, name="b.sqlite")
    for rid in ("REQ-003", "REQ-007", "REQ-009"):
        a = seq.submit(rid)
        import shutil
        shutil.rmtree(audit.team_dir() / a["case_id"])
        b = par.submit(rid, on_event=lambda *_: None)
        assert (a["decision"], a["flags"], a["missing_items"]) == (b["decision"], b["flags"], b["missing_items"])
    seq.close(); par.close()


def test_injection_cases_skip_nothing_and_go_to_a_person(desk):
    for rid in ("REQ-011", "REQ-016", "REQ-017"):
        case = desk.submit(rid)
        assert case["status"] == "STOPPED" and "possible_injection" in case["flags"]
        assert {"documents", "duplicate", "watchlist", "bank"} <= set(case["raw"])
        assert case["vendor_id"] is None


def test_all_19_cases_through_the_team_match_the_expected_results(db, runs, tmp_path):
    d = make_desk(db, tmp_path)
    for row in load_cases():
        rid = row["request_file"].removesuffix(".txt")
        case = d.reply("VOB-" + row["id"][4:7], rid) if "-R" in row["id"] else d.submit(rid)
        assert case["decision"] == row["expected_decision"], row["id"]
        assert set(case["missing_items"]) == split(row["expected_missing"]), row["id"]
        assert split(row["expected_flags"]) <= set(case["flags"]), row["id"]
        if row["expected_approvers"]:
            assert case["approvers_required"] == int(row["expected_approvers"]), row["id"]
    assert vendor_count(db) == 20          # no vendor is created by running checks
    d.close()


# ------------------------------------------------------------------ replies resume the same case
def test_a_vendor_reply_resumes_the_same_case_from_its_checkpoint_even_after_a_restart(db, runs, tmp_path):
    d = make_desk(db, tmp_path)
    case = d.submit("REQ-001")
    assert case["status"] == "WAITING_FOR_VENDOR" and case["draft_email"]["sent"] is False
    first_calls = case["usage"]["tool_calls"]
    d.close()
    d2 = make_desk(db, tmp_path)                       # a new process: only the checkpoint file survives
    lines = []
    case = d2.reply("VOB-001", "REQ-001-R1", on_event=lines.append)
    assert case["status"] == "READY_FOR_APPROVAL" and case["request_ids"] == ["REQ-001", "REQ-001-R1"]
    assert case["usage"]["tool_calls"] - first_calls <= 2           # only the documents check ran again
    assert any("reply affects documents" in l for l in lines) and not any("supervisor -> compliance" in l for l in lines)
    assert [m["to_state"] for m in case["moves"]][-3:] == ["WAITING_FOR_VENDOR", "CHECKING", "READY_FOR_APPROVAL"]
    d2.close()


def test_a_reply_is_refused_for_a_case_that_is_not_waiting(desk):
    desk.submit("REQ-002")
    with pytest.raises(ValueError):
        desk.reply("VOB-002", "REQ-001-R1")


# ------------------------------------------------------------------ Phase 10: the gate and the one write
def test_one_approver_below_the_threshold_creates_exactly_one_vendor(db, desk):
    case = desk.submit("REQ-008")
    assert case["status"] == "READY_FOR_APPROVAL" and case["approvers_required"] == 1 and desk.waiting_at_gate("VOB-008")
    assert vendor_count(db) == 20                                  # nothing written while waiting
    out = desk.act("VOB-008", "approve", "alex@example.com", "evidence checked")
    assert out["ok"] and out["case"]["status"] == "CREATED" and out["case"]["vendor_id"] == "VEN-1021"
    assert vendor_count(db) == 21


def test_two_different_approvers_above_the_threshold(db, desk):
    desk.submit("REQ-009")
    first = desk.act("VOB-009", "approve", "alex@example.com")
    assert first["case"]["status"] == "READY_FOR_APPROVAL" and first["case"]["next_step"] == "approver 2 of 2"
    assert vendor_count(db) == 20
    same = desk.act("VOB-009", "approve", "Alex@Example.com")      # same person, different capitals
    assert not same["ok"] and "cannot approve twice" in same["message"]
    assert vendor_count(db) == 20 and desk.case("VOB-009")["status"] == "READY_FOR_APPROVAL"
    second = desk.act("VOB-009", "approve", "sam@example.com")
    assert second["case"]["status"] == "CREATED" and vendor_count(db) == 21
    approvals = [a["approver"] for a in second["case"]["approvals"]]
    assert approvals == ["alex@example.com", "sam@example.com"]


def test_approving_an_approved_case_twice_leaves_one_vendor(db, desk):
    desk.submit("REQ-008")
    desk.act("VOB-008", "approve", "alex@example.com")
    again = desk.act("VOB-008", "approve", "alex@example.com")
    assert not again["ok"] and "not allowed while the case is CREATED" in again["message"]
    assert vendor_count(db) == 21
    # even if the create step itself runs again (a resumed or replayed graph), nothing more is written
    out = desk.team.create({"case_id": "VOB-008"})
    assert "already created" in out["log"][0] and vendor_count(db) == 21
    # and the write itself is keyed by the case id
    w = LocalWriter(db)
    r1 = w.create("VOB-008", ["REQ-008"], ["a@example.com"], 1, 30)
    r2 = w.create("VOB-008", ["REQ-008"], ["a@example.com"], 1, 30)
    assert r1["vendor_id"] == r2["vendor_id"] and not r2["created"] and vendor_count(db) == 21


def test_nothing_is_written_for_cases_that_are_rejected_stopped_or_waiting(db, desk):
    desk.submit("REQ-003")                       # recommended reject -> STOPPED, a person confirms
    desk.submit("REQ-004")                       # stop for a person
    desk.submit("REQ-012")                       # waiting for vendor
    desk.submit("REQ-011")                       # injection
    assert {desk.case(c)["status"] for c in ("VOB-003", "VOB-004", "VOB-012", "VOB-011")} == {"STOPPED", "WAITING_FOR_VENDOR"}
    for cid in ("VOB-003", "VOB-004", "VOB-012", "VOB-011"):
        out = desk.act(cid, "approve", "alex@example.com")
        assert not out["ok"], cid
    out = desk.act("VOB-003", "reject", "alex@example.com", "same tax ID as VEN-1001")
    assert out["case"]["status"] == "REJECTED"
    assert vendor_count(db) == 20


def test_a_stopped_case_needs_a_person_to_release_it_before_it_can_be_approved(db, desk):
    desk.submit("REQ-004")
    assert desk.case("VOB-004")["status"] == "STOPPED"
    rel = desk.act("VOB-004", "release", "alex@example.com", "the name difference is real, different owners")
    assert rel["case"]["status"] == "READY_FOR_APPROVAL"
    done = desk.act("VOB-004", "approve", "alex@example.com")
    assert done["case"]["status"] == "CREATED" and vendor_count(db) == 21
    # a recommended rejection cannot be released, only confirmed or re-run
    desk.submit("REQ-005")
    assert not desk.act("VOB-005", "release", "alex@example.com")["ok"]


def test_ask_the_vendor_sends_the_case_to_waiting_with_a_draft_and_the_reply_resumes_it(db, desk):
    desk.submit("REQ-002")
    out = desk.act("VOB-002", "ask_vendor", "alex@example.com", "Please confirm your trading address.")
    case = out["case"]
    assert case["status"] == "WAITING_FOR_VENDOR" and "trading address" in case["draft_email"]["body"]
    assert case["draft_email"]["sent"] is False and vendor_count(db) == 20
    assert not desk.act("VOB-002", "approve", "alex@example.com")["ok"]


def test_the_approver_screen_data_has_no_private_values(db, desk):
    desk.submit("REQ-008")
    desk.act("VOB-008", "approve", "alex@example.com")
    text = json.dumps(desk.case("VOB-008")) + "".join(p.read_text(encoding="utf-8") for p in
                                                       (audit.team_dir() / "VOB-008").glob("*.json*"))
    for secret in ("99519346", "99-51-93"):
        assert secret not in text


def test_a_decision_needs_a_named_person(desk):
    desk.submit("REQ-008")
    assert not desk.act("VOB-008", "approve", "  ")["ok"]
    assert desk.case("VOB-008")["status"] == "READY_FOR_APPROVAL"


def test_a_system_failure_ends_in_stopped_and_a_person_can_rerun_it(db, runs, tmp_path):
    class Failing(Toolbox):
        def call(self, name, args):
            return {"error": "the documents service is down"} if name == "check_documents" else super().call(name, args)

    d = make_desk(db, tmp_path, backend=Failing(db_path=db))
    case = d.submit("REQ-002")
    assert case["status"] == "STOPPED" and "tool errors" in case["stop_reason"] or "documents specialist stopped" in case["stop_reason"]
    assert not d.waiting_at_gate("VOB-002")
    assert vendor_count(db) == 20
    d.backend = d.team.backend = Toolbox(db_path=db)               # the service is back
    out = d.act("VOB-002", "rerun", "alex@example.com", "service restored")
    assert out["case"]["status"] == "READY_FOR_APPROVAL"
    d.close()


# ------------------------------------------------------------------ policy §9
def test_stale_cases_go_to_the_manager_then_expire_and_are_never_approved(db, desk):
    desk.submit("REQ-008")
    desk.submit("REQ-002")
    now = datetime.now(timezone.utc)
    assert desk.escalate_stale(now + timedelta(days=1)) == []
    done = desk.escalate_stale(now + timedelta(days=3))
    assert len(done) == 2 and all("manager's queue" in x for x in done)
    assert desk.case("VOB-008")["manager_queue"] and desk.case("VOB-008")["status"] == "READY_FOR_APPROVAL"
    assert any(e["event"] == "reminder" for e in audit.read("VOB-008"))
    assert desk.escalate_stale(now + timedelta(days=3)) == []        # no second reminder
    done = desk.escalate_stale(now + timedelta(days=8))
    assert all("stopped" in x for x in done)
    assert desk.case("VOB-008")["status"] == "STOPPED" and "approval expired" in desk.case("VOB-008")["stop_reason"]
    assert vendor_count(db) == 20
    assert not desk.act("VOB-008", "approve", "alex@example.com")["ok"]


# ------------------------------------------------------------------ the audit trail
def test_the_audit_trail_records_everything_and_is_intact(desk):
    desk.submit("REQ-009")
    desk.act("VOB-009", "approve", "alex@example.com", "ok")
    desk.act("VOB-009", "approve", "sam@example.com", "ok")
    entries = audit.read("VOB-009")
    events = {e["event"] for e in entries}
    assert {"request_received", "tool_call", "handoff", "verdict", "state_change", "decision", "write"} <= events
    assert {e["who"] for e in entries} >= {"intake", "documents", "compliance", "finance", "reviewer", "alex@example.com", "sam@example.com", "system"}
    assert audit.verify("VOB-009")[0]
    assert [e["at"] for e in entries] == sorted(e["at"] for e in entries)


def test_create_through_the_mcp_server_with_writes_on_for_that_call_only(db, runs, tmp_path):
    from vendor_desk.mcp_client import McpBackend
    from vendor_desk.team import McpWriter
    reader = McpBackend()                                      # the everyday server: writes OFF
    try:
        assert "create_vendor" not in reader.tool_names()
        d = CaseDesk(OfflineLLM(), reader, McpWriter(), False, tmp_path / "cp.sqlite")
        d.submit("REQ-008")
        out = d.act("VOB-008", "approve", "alex@example.com")
        assert out["case"]["status"] == "CREATED" and out["case"]["vendor_id"] == "VEN-1021"
        assert "create_vendor" not in reader.tool_names()      # still off for everyone else
        d.close()
    finally:
        reader.close()
    assert vendor_count(db) == 21


# ------------------------------------------------------------------ stretch: a model as supervisor
def test_a_model_supervisor_gives_the_same_decisions_and_costs_extra_calls(db, runs, tmp_path):
    rule = make_desk(db, tmp_path, name="r.sqlite")
    model = CaseDesk(OfflineLLM(), Toolbox(db_path=db), LocalWriter(db), False, tmp_path / "m.sqlite", supervisor_mode="model")
    import shutil
    a = rule.submit("REQ-007")
    shutil.rmtree(audit.team_dir() / "VOB-007")
    lines = []
    b = model.submit("REQ-007", on_event=lines.append)
    assert (a["decision"], a["flags"], a["missing_items"]) == (b["decision"], b["flags"], b["missing_items"])
    assert any("[chosen by the model]" in l for l in lines)
    assert b["usage"]["model_calls"] > a["usage"]["model_calls"] and "supervisor" in b["per_role"]
    rule.close(); model.close()


def test_a_model_supervisor_that_picks_an_illegal_step_is_overruled_by_the_rule(db, runs, tmp_path):
    d = CaseDesk(OfflineLLM(faults={"supervisor": "wrong"}), Toolbox(db_path=db), LocalWriter(db), False,
                 tmp_path / "m.sqlite", supervisor_mode="model")
    lines = []
    case = d.submit("REQ-002", on_event=lines.append)
    assert case["status"] == "READY_FOR_APPROVAL" and any("not allowed; rule used" in l for l in lines)
    assert any(e["event"] == "refused" and e["who"] == "supervisor" for e in audit.read("VOB-002"))
    d.close()
