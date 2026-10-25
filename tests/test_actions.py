"""Phase 7: changes only through an approval that names one step on one service, with the right approvers, once."""
import pytest
from pydantic import ValidationError

from tower.actions import ActionError, actions_log_lines
from tower.models import ActionRequest, ApprovalIn
from tower.tools import ToolGateway, change_tool_names, read_tool_names


def inc_of(tower, alert_id):
    return next(i for i in tower.list_incidents() if alert_id in i.alert_ids)


def decide(tower, rid, who, reason="", decision="approve"):
    return tower.actions.decide_safely(rid, ApprovalIn(approver=who, reason=reason, decision=decision))


def lines(tower):
    return actions_log_lines(tower.s.actions_log)


def test_no_approval_means_no_action(triaged):
    inc = inc_of(triaged, "AL-101")
    assert inc.request_id and inc.status == "WAITING_FOR_APPROVAL"
    assert lines(triaged) == []


def test_one_approval_is_enough_for_s09_and_it_runs_once(triaged):
    inc = inc_of(triaged, "AL-120")
    assert inc.approvals_needed == 1
    out = decide(triaged, inc.request_id, "M. Sato")
    assert out["status"] == "CHANGE_DONE" and out["executed_now"]
    assert len(lines(triaged)) == 1 and "restart_service on hr-selfservice" in lines(triaged)[0]
    assert triaged.get_incident(inc.incident_id).status == "CHANGE_DONE"


def test_a_second_approval_of_the_same_request_writes_nothing_new(triaged):
    inc = inc_of(triaged, "AL-120")
    decide(triaged, inc.request_id, "M. Sato")
    again = decide(triaged, inc.request_id, "M. Sato")
    assert again["executed_now"] is False and "already executed" in again["note"]
    assert len(lines(triaged)) == 1


def test_s07_needs_two_approvals_from_two_people_and_a_reason(triaged):
    inc = inc_of(triaged, "AL-118")
    assert inc.approvals_needed == 2 and inc.freeze
    with pytest.raises(ActionError, match="written reason"):
        decide(triaged, inc.request_id, "L. Brandt")  # freeze: reason required
    out = decide(triaged, inc.request_id, "L. Brandt", "node 2 leaking memory, node 1 healthy")
    assert out["status"] == "PENDING" and out["waiting_for"] == ["K. Adeyemi"] and lines(triaged) == []
    with pytest.raises(ActionError, match="already approved"):
        decide(triaged, inc.request_id, "L. Brandt", "approving again with a reason")  # one person cannot approve twice
    assert lines(triaged) == []
    out = decide(triaged, inc.request_id, "K. Adeyemi", "freeze: tier 1, P2, owner has approved")
    assert out["status"] == "CHANGE_DONE" and len(lines(triaged)) == 1


def test_s03_p1_needs_the_duty_manager_too(triaged):
    inc = inc_of(triaged, "AL-105")
    assert [a.engineer for a in inc.approvers] == ["D. Osei", "K. Adeyemi"]
    decide(triaged, inc.request_id, "D. Osei")
    assert lines(triaged) == []
    decide(triaged, inc.request_id, "K. Adeyemi")
    assert "failover_db on db-core" in lines(triaged)[0]


def test_someone_who_is_not_an_approver_is_refused(triaged):
    inc = inc_of(triaged, "AL-101")
    with pytest.raises(ActionError) as e:
        decide(triaged, inc.request_id, "M. Sato")
    assert e.value.code == 403 and lines(triaged) == []


def test_rejection_stops_the_request(triaged):
    inc = inc_of(triaged, "AL-101")
    decide(triaged, inc.request_id, "T. Mwangi", "not now", decision="reject")
    assert triaged.get_incident(inc.incident_id).status == "REJECTED"
    with pytest.raises(ActionError):
        decide(triaged, inc.request_id, "T. Mwangi")
    assert lines(triaged) == []


def test_one_request_cannot_name_two_services():
    for bad in ("payportal,hr-selfservice", "payportal;intranet", "payportal intranet", ""):
        with pytest.raises(ValidationError):
            ActionRequest(incident_id="INC-3007", runbook_id="RB-02", step_no=3, action="restart_service", target_service=bad, reason="x y z")


def test_a_request_must_match_the_incident_and_the_runbook(triaged):
    inc = inc_of(triaged, "AL-118")
    con = triaged.con()
    base = dict(incident_id=inc.incident_id, runbook_id="RB-02", step_no=3, action="restart_service", reason="restart one node")
    with pytest.raises(ActionError, match="root cause"):
        triaged.actions.create(con, ActionRequest(**base, target_service="intranet"), inc)
    with pytest.raises(ActionError, match="not a runbook listed"):
        triaged.actions.create(con, ActionRequest(**{**base, "runbook_id": "RB-04"}, target_service="payportal"), inc)
    with pytest.raises(ActionError, match="not a \\[CHANGE\\]"):
        triaged.actions.create(con, ActionRequest(**{**base, "step_no": 1, "action": "check_memory_trend"}, target_service="payportal"), inc)
    assert lines(triaged) == []


def test_the_creating_the_same_request_twice_is_one_request(triaged):
    inc = inc_of(triaged, "AL-101")
    con = triaged.con()
    req = ActionRequest(incident_id=inc.incident_id, runbook_id="RB-04", step_no=2, action="clear_temp_files", target_service="fs-02", reason="clear tmp")
    a, b = triaged.actions.create(con, req, inc), triaged.actions.create(con, req, inc)
    con.commit()
    assert a["request_id"] == b["request_id"] == inc.request_id
    assert con.execute("SELECT COUNT(*) FROM action_requests WHERE incident_id=?", (inc.incident_id,)).fetchone()[0] == 1


def test_the_audit_trail_has_no_secrets(triaged):
    inc = inc_of(triaged, "AL-119")
    decide(triaged, inc.request_id, "R. Iyer", "Winter2026! was in the alert; password=Winter2026! blocked 203.0.113.45")
    con = triaged.con()
    text = " ".join(r["detail"] for r in con.execute("SELECT detail FROM audit"))
    assert "Winter2026" not in text and "900318" not in text


# ---- tool lists ----
def test_two_lists_of_tools(triaged):
    cat = triaged.cat
    reads, changes = read_tool_names(cat), change_tool_names(cat)
    assert reads.isdisjoint(changes)
    assert {"failover_db", "restart_service", "clear_cache", "block_source_ip"} <= changes
    assert "page_oncall" in reads and "personal_mobile" not in reads | changes
    assert not any("mobile" in t or "phone" in t for t in reads | changes)


def test_a_model_calling_a_change_tool_is_refused_and_audited(triaged):
    r = triaged.gateway.call("restart_service", service="payportal", actor="model")
    assert not r.ok and "CHANGE" in r.text and lines(triaged) == []
    con = triaged.con()
    assert con.execute("SELECT COUNT(*) FROM audit WHERE event='tool_refused'").fetchone()[0] >= 1


def test_read_tools_run_and_are_labelled_simulated(triaged):
    r = triaged.gateway.call("check_cache_health", service="cache-redis")
    assert r.ok and r.simulated and "evictions" in r.text
    assert not triaged.gateway.call("drop_tables", service="x").ok


def test_page_oncall_never_returns_a_phone_number(triaged):
    r = triaged.gateway.call("page_oncall", args={"team": "Identity"})
    assert r.ok and "R. Iyer" in r.text and "900" not in r.text
    assert not triaged.gateway.call("page_oncall", args={"team": "Nobody"}).ok
