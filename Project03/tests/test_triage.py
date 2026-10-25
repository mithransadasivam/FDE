"""Phase 2: triage is plain Python. These tests use no model at all and must score 10 of 10 on the rule checks."""
from datetime import datetime

import pytest

from tower.evaluate import CHECKS_RULES, load_scenarios, score
from tower.triage import in_freeze
from tests.conftest import mk


def test_ten_incidents_from_22_alerts(tower):
    incs = tower.triage_rules(tower.starter_alerts())
    assert len(incs) == 10
    assert sum(len(i.alert_ids) for i in incs) == 22


def test_rule_checks_score_10_of_10_with_no_model(tower):
    incs = tower.triage_rules(tower.starter_alerts())
    res = score(incs)
    for check in ("grouping", "root_cause", "severity", "approvals", "similar"):
        assert res["summary"][check] == 10, (check, [r for r in res["rows"] if not r[check]])


@pytest.mark.parametrize("sc", load_scenarios(), ids=lambda s: s["scenario"])
def test_each_scenario(tower, sc):
    incs = tower.triage_rules(tower.starter_alerts())
    res = score(incs, [sc])
    row = res["rows"][0]
    for c in ("grouping", "root_cause", "severity", "approvals", "similar"):
        assert row[c], (sc["scenario"], c, row.get("got"), row.get("want"))


def test_s03_root_cause_is_furthest_down_the_chain(tower):
    inc = next(i for i in tower.triage_rules(tower.starter_alerts()) if "AL-105" in i.alert_ids)
    assert inc.root_cause == "db-core"
    assert set(inc.services) == {"db-core", "payportal", "hr-selfservice", "ticketing-api"}
    assert inc.severity == "P1"
    assert any(r.startswith("2.2") for r in inc.rules_applied)


def test_s07_freeze_needs_two_and_is_not_p1(tower):
    inc = next(i for i in tower.triage_rules(tower.starter_alerts()) if i.alert_ids == ["AL-118"])
    assert inc.severity == "P2" and inc.freeze and inc.approvals_needed == 2
    assert [a.team for a in inc.approvers] == ["Finance Apps", "Duty manager"]
    assert any(r.startswith("5.3") for r in inc.rules_applied)


def test_s09_one_approval_because_tier_2_is_outside_the_freeze_rule(tower):
    inc = next(i for i in tower.triage_rules(tower.starter_alerts()) if "AL-120" in i.alert_ids)
    assert inc.approvals_needed == 1 and not inc.freeze


def test_s10_unknown_service_needs_a_person_and_nothing_else(tower):
    inc = next(i for i in tower.triage_rules(tower.starter_alerts()) if i.alert_ids == ["AL-122"])
    assert inc.status == "NEEDS_PERSON" and inc.root_cause is None and inc.severity is None
    assert inc.approvals_needed == 0 and inc.flags == ["unknown service"]
    assert any(r.startswith("3.3") for r in inc.rules_applied)


def test_s04_flapping_is_auto_resolved_p4(tower):
    inc = next(i for i in tower.triage_rules(tower.starter_alerts()) if "AL-110" in i.alert_ids)
    assert (inc.status, inc.severity, inc.approvals_needed) == ("AUTO_RESOLVED", "P4", 0)


def test_same_service_16_minutes_apart_is_two_incidents(tower):
    incs = tower.triage_rules([mk("A1", "2026-10-21 10:00", "fs-02"), mk("A2", "2026-10-21 10:16", "fs-02")])
    assert len(incs) == 2


def test_dependency_alerts_11_minutes_apart_are_not_merged(tower):
    incs = tower.triage_rules([mk("A1", "2026-10-21 10:00", "db-core", "availability", "critical"),
                               mk("A2", "2026-10-21 10:11", "payportal", "http_check", "critical")])
    assert len(incs) == 2


def test_unrelated_services_at_the_same_time_stay_separate(tower):
    incs = tower.triage_rules([mk("A1", "2026-10-21 10:00", "fs-02", "disk_space", "warning"),
                               mk("A2", "2026-10-21 10:01", "mail-gw", "cert_expiry", "warning")])
    assert len(incs) == 2


def test_two_services_one_root_cause_is_p3_not_p1(tower):
    incs = tower.triage_rules([mk("A1", "2026-10-21 10:00", "cache-redis", "memory", "warning"),
                               mk("A2", "2026-10-21 10:01", "ticketing-api", "error_rate", "major")])
    assert incs[0].severity == "P3"  # only two services: not P1


@pytest.mark.parametrize("when,expected", [
    ("2026-10-23 17:59", False), ("2026-10-23 18:00", True), ("2026-10-24 12:00", True), ("2026-10-25 23:59", True),
    ("2026-10-26 05:59", True), ("2026-10-26 06:00", False), ("2026-10-22 23:40", False)])
def test_freeze_window_boundaries(when, expected):
    assert in_freeze(datetime.strptime(when, "%Y-%m-%d %H:%M")) is expected


def test_similar_incident_is_evidence_not_an_order(tower):
    inc = next(i for i in tower.triage_rules(tower.starter_alerts()) if "AL-103" in i.alert_ids)
    assert inc.similar_incident == "INC-2291"  # cache was the cause, not the deploy
    assert inc.root_cause == "cache-redis"
