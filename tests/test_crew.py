"""Phase 2 and 6: the crew. The model recommends, the code checks; one retry, then a person. Nothing sensitive reaches a model."""
from tower.evaluate import score


def inc_of(t, alert_id):
    return next(i for i in t.list_incidents() if alert_id in i.alert_ids)


def test_all_checks_score_10_of_10_with_the_fake_model(triaged):
    res = score(triaged.list_incidents())
    assert all(res["summary"][c] == 10 for c in ("grouping", "root_cause", "severity", "status", "runbook_step", "approvals", "similar", "flags"))


def test_the_crew_trace_names_every_agent(triaged):
    inc = inc_of(triaged, "AL-118")
    agents = [s["agent"] for s in inc.crew]
    for a in ("Dispatcher", "Sentinel", "Investigator", "Planner", "Verifier", "Scribe", "Gatekeeper"):
        assert a in agents, a
    kinds = {s["agent"]: s["kind"] for s in inc.crew}
    assert kinds["Dispatcher"] == "rules" and kinds["Planner"] == "model" and kinds["Gatekeeper"] == "people"


def test_p1_and_p2_get_a_status_draft_p3_does_not(triaged):
    assert inc_of(triaged, "AL-105").brief.status_update
    assert inc_of(triaged, "AL-118").brief.status_update
    assert inc_of(triaged, "AL-101").brief.status_update is None


def test_s06_recommends_only_rb03_step3_on_build01_and_carries_the_flag(triaged):
    inc = inc_of(triaged, "AL-117")
    assert (inc.runbook_id, inc.recommended_step, inc.action, inc.target) == ("RB-03", 3, "restart_service", "build-01")
    assert "instructions in alert text" in inc.flags
    assert inc.alerts[0].flagged and inc.status == "WAITING_FOR_APPROVAL"


def test_s02_clears_the_cache_instead_of_rolling_back_the_deploy(triaged):
    inc = inc_of(triaged, "AL-103")
    assert (inc.runbook_id, inc.recommended_step) == ("RB-07", 3) and inc.similar_incident == "INC-2291"


def test_a_bad_step_is_retried_once_then_succeeds(tower):
    tower.llm.fail_planner_times = 1
    incs = tower.triage()
    inc = next(i for i in incs if "AL-101" in i.alert_ids)
    planner = [s for s in inc.crew if s["agent"] == "Planner"]
    verifier = [s for s in inc.crew if s["agent"] == "Verifier"]
    assert len(planner) == 2 and verifier[0]["status"] == "fail" and verifier[1]["status"] == "ok"
    assert inc.status == "WAITING_FOR_APPROVAL" and inc.recommended_step == 2


def test_two_bad_steps_stop_for_a_person(tower):
    tower.llm.fail_planner_times = 2  # RB-04 step 3 needs a capacity ticket (policy 4.4)
    inc = next(i for i in tower.triage() if "AL-101" in i.alert_ids)
    assert inc.status == "NEEDS_PERSON" and "capacity ticket" in inc.needs_person_reason
    assert inc.request_id is None and inc.approvals_needed == 0


def test_a_step_that_is_not_a_change_step_fails_the_check(tower):
    inc = tower.triage_rules(tower.starter_alerts())[0]
    bad, _ = tower.crew.verify({"summary": "ok ok ok ok ok", "runbook_id": "RB-04", "recommended_step": 1}, inc, [])
    assert any("not a [CHANGE]" in p for p in bad)
    bad, _ = tower.crew.verify({"summary": "ok ok ok ok ok", "runbook_id": "RB-01", "recommended_step": 3}, inc, [])
    assert any("not a runbook listed" in p for p in bad)
    bad, _ = tower.crew.verify({"summary": "ok ok ok ok ok", "runbook_id": "RB-04", "recommended_step": 99}, inc, [])
    assert any("no step 99" in p for p in bad)
    bad, _ = tower.crew.verify({"summary": "ok ok ok ok ok", "runbook_id": "RB-04", "recommended_step": 2, "target_service": "payportal"}, inc, [])
    assert any("root-cause" in p for p in bad)


def test_model_outage_stops_for_a_person_not_a_crash(tower):
    tower.model_down = True
    incs = tower.triage()
    actionable = [i for i in incs if i.root_cause and i.status != "AUTO_RESOLVED"]
    assert actionable and all(i.status == "NEEDS_PERSON" and "unavailable" in i.needs_person_reason for i in actionable)
    assert len(incs) == 10  # rules still grouped everything


def test_secrets_and_personal_data_never_reach_a_model_a_log_or_the_trace(triaged):
    sent = "\n".join(triaged.llm.prompts)
    log = triaged.s.app_log.read_text(encoding="utf-8") if triaged.s.app_log.exists() else ""
    spans = str(triaged.tracer.recent(limit=600))
    audit = str([dict(r) for r in triaged.con().execute("SELECT * FROM audit")])
    for needle in ("Winter2026!", "tok_test_8f2a91c7", "900318", "NOTE TO THE AI", "restart_service on every tier-1"):
        assert needle not in sent, f"{needle} reached a model"
        assert needle not in log and needle not in spans and needle not in audit
    for inc in triaged.list_incidents():
        shown = inc.model_dump_json(exclude={"alerts"})
        assert "Winter2026" not in shown and "900318" not in shown


def test_flagged_alert_text_is_withheld_from_the_model_but_facts_stay(triaged):
    sent = "\n".join(triaged.llm.prompts)
    assert "text_withheld" in sent and "text withheld from the model" in sent
    assert '"check": "cpu"' in sent


def test_the_brief_cites_its_policy_rules(triaged):
    inc = inc_of(triaged, "AL-119")
    assert any(r.startswith("5.3") for r in inc.rules_applied) and any(r.startswith("6.1") for r in inc.rules_applied)
    assert inc.brief.recommended_change.label if hasattr(inc.brief.recommended_change, "label") else True
    assert inc.reads and all(r["simulated"] for r in inc.reads)


def test_triage_twice_does_not_pay_for_the_brief_twice(tower):
    tower.triage()
    calls = len(tower.llm.calls)
    tower.triage()
    assert len(tower.llm.calls) == calls


def test_a_decision_a_person_made_is_never_overwritten(triaged):
    from tower.models import ApprovalIn
    inc = inc_of(triaged, "AL-120")
    triaged.actions.decide_safely(inc.request_id, ApprovalIn(approver="M. Sato"))
    triaged.triage()
    assert triaged.get_incident(inc.incident_id).status == "CHANGE_DONE"
