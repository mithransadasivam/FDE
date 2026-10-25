"""Triage in plain Python, no model: group alerts, find the root cause, set severity, status, similar incident and approvals.

Every rule cites its policy section in `rules_applied`. The model never touches anything in this file.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from .catalog import Catalog
from .models import Alert, Approver, Incident

TIME_FMT = "%Y-%m-%d %H:%M"
SEV_ORDER = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}

# What a monitoring check means in the words past incidents use (policy 6.1: "the same symptom")
SYMPTOM_TAGS = {
    "disk_space": ["disk space"], "memory": ["high memory"], "error_rate": ["api errors"],
    "availability": ["unavailable", "degraded"], "latency": ["latency"], "cert_expiry": ["certificate expiring"],
    "cpu": ["high cpu"], "auth_failures": ["authentication failures"],
    "http_check": ["slow responses"], "login_journey": ["slow responses"], "payslip_journey": ["slow responses"],
}
# Which runbook a check points to. Used only when no model is involved (auto-resolved incidents) and as a hint.
RUNBOOK_FOR_CHECK = {
    "disk_space": "RB-04", "cpu": "RB-03", "auth_failures": "RB-05", "cert_expiry": "RB-06", "latency": "RB-08",
    "memory": "RB-02", "http_check": "RB-02", "login_journey": "RB-02", "payslip_journey": "RB-02",
    "error_rate": "RB-07", "availability": "RB-01",
}


def runbook_hint(rc: str, check: str, cat: Catalog) -> str | None:
    """A hint only: the runbook must be one listed for the root-cause service (4.1). The model chooses; code checks."""
    listed = cat.services[rc].runbooks
    hint = RUNBOOK_FOR_CHECK.get(check)
    return hint if hint in listed else (listed[0] if listed else None)


def t(s: str) -> datetime:
    return datetime.strptime(s, TIME_FMT)


def in_freeze(when: datetime) -> bool:
    """Policy 5.3: Friday 18:00 to Monday 06:00."""
    wd = when.weekday()  # Mon=0
    if wd == 4:
        return when.hour >= 18
    if wd in (5, 6):
        return True
    if wd == 0:
        return when.hour < 6
    return False


def group_alerts(alerts: list[Alert], cat: Catalog) -> list[list[Alert]]:
    """Policy 3.1 (same service within 15 minutes) then 3.2 (a service and its dependencies within 10 minutes)."""
    ordered = sorted(alerts, key=lambda a: (t(a.time), a.alert_id))
    clusters: list[list[Alert]] = []
    last_by_service: dict[str, tuple[int, datetime]] = {}
    for a in ordered:
        at = t(a.time)
        prev = last_by_service.get(a.service)
        if prev and at - prev[1] <= timedelta(minutes=15):
            clusters[prev[0]].append(a)
            last_by_service[a.service] = (prev[0], at)
        else:
            clusters.append([a])
            last_by_service[a.service] = (len(clusters) - 1, at)

    parent = list(range(len(clusters)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def related(x: str, y: str) -> bool:
        if x == y or not (cat.known(x) and cat.known(y)):
            return False
        return y in cat.deps_closure(x) or x in cat.deps_closure(y)

    for i in range(len(clusters)):
        for j in range(i + 1, len(clusters)):
            si, sj = clusters[i][0].service, clusters[j][0].service
            if not related(si, sj):
                continue
            close = any(abs(t(a.time) - t(b.time)) <= timedelta(minutes=10) for a in clusters[i] for b in clusters[j])
            if close:
                parent[find(j)] = find(i)

    merged: dict[int, list[Alert]] = {}
    for i, c in enumerate(clusters):
        merged.setdefault(find(i), []).extend(c)
    groups = [sorted(g, key=lambda a: (t(a.time), a.alert_id)) for g in merged.values()]
    return sorted(groups, key=lambda g: (t(g[0].time), g[0].alert_id))


def root_cause(group: list[Alert], cat: Catalog) -> str | None:
    """Policy 3.2: the alerting service the others depend on, furthest down the chain. None for an unknown service (3.3)."""
    services = sorted({a.service for a in group})
    if any(not cat.known(s) for s in services):
        return None
    candidates = [s for s in services if not (cat.deps_closure(s) & (set(services) - {s}))]
    first_alert = {s: min(t(a.time) for a in group if a.service == s) for s in services}
    return sorted(candidates, key=lambda s: (-len(set(cat.dependants(s)) & set(services)), first_alert[s], s))[0]


def is_flapping(group: list[Alert]) -> bool:
    """Policy 2.5 and 3.4: every alert cleared by itself within 15 minutes and needs no action."""
    if all(a.severity == "info" for a in group):
        return True
    by_key: dict[tuple[str, str], list[Alert]] = {}
    for a in group:
        by_key.setdefault((a.service, a.check), []).append(a)
    for alerts in by_key.values():
        alerts.sort(key=lambda a: t(a.time))
        if alerts[-1].status != "resolved":
            return False
        for i, a in enumerate(alerts):
            if a.status == "firing":
                nxt = next((b for b in alerts[i + 1:] if b.status == "resolved"), None)
                if nxt is None or t(nxt.time) - t(a.time) > timedelta(minutes=15):
                    return False
    return True


def severity_of(group: list[Alert], cat: Catalog, rc: str) -> tuple[str, list[str]]:
    """Section 2. Returns the severity and the clauses that decided it."""
    rules: list[str] = []
    best = "P4"

    def bump(sev: str, why: str):
        nonlocal best
        if SEV_ORDER[sev] < SEV_ORDER[best]:
            best = sev
        rules.append(why)

    affected = sorted({a.service for a in group if a.severity != "info"})
    for s in affected:
        svc = cat.services[s]
        worst_down = any(a.service == s and a.severity == "critical" for a in group)
        cert = any(a.service == s and a.check == "cert_expiry" for a in group)
        if svc.tier == 1:
            bump("P1", f"2.2 P1: {s} is tier 1 and down") if worst_down else bump("P2", f"2.3 P2: {s} is tier 1 and degraded")
        elif svc.tier == 2:
            bump("P2", f"2.3 P2: {s} is tier 2 and down") if worst_down else bump("P3", f"2.4 P3: {s} is tier 2 and degraded")
        else:
            bump("P3", f"2.4 P3: {s} is tier 3 and {'down' if worst_down else 'degraded'}")
        if cert:
            rules.append("2.4 P3: a warning that needs action within 7 days (certificate)")
    if len(affected) >= 3:
        bump("P1", f"2.2 P1: {len(affected)} services are affected by one root cause ({rc})")
    rules.append(f"2.6 severity is the highest that applies to any service in the incident: {best}")
    return best, rules


def symptom_tags(group: list[Alert], rc: str) -> set[str]:
    tags: set[str] = set()
    for a in group:
        if a.service == rc:
            tags.update(SYMPTOM_TAGS.get(a.check, []))
    return tags


def similar_incident(group: list[Alert], rc: str, severity: str, cat: Catalog) -> str | None:
    """Policy 6.1: a past incident on the same service with the same symptom. A past fix is evidence, not an order (6.2)."""
    tags = symptom_tags(group, rc)
    best, best_score = None, 0
    for h in cat.history:
        score = 0
        if h["root_cause_service"] == rc:
            score += 4
        elif h["service"] == rc:
            score += 2
        if any(tag in h["symptom"].lower() for tag in tags):
            score += 3
        if h["severity"] == severity:
            score += 1
        if score > best_score:
            best, best_score = h["incident_id"], score
    return best if best_score >= 4 else None


def approvers_for(inc_sev: str, rc: str, opened: datetime, cat: Catalog) -> tuple[list[Approver], bool, list[str]]:
    """Section 5. 1 = the owning team's on-call; 2 adds the duty manager (P1, or tier 1 in the change freeze)."""
    owner = cat.owner(rc)
    out = [Approver(role="owner", team=owner["team"], engineer=owner["engineer"], why=f"owns {rc} (5.1)")]
    rules = [f"5.1 the on-call engineer of {owner['team']} approves a change to {rc}"]
    freeze = in_freeze(opened) and cat.services[rc].tier == 1
    dm = cat.duty_manager()
    if inc_sev == "P1":
        out.append(Approver(role="duty_manager", team=dm["team"], engineer=dm["engineer"], why="P1 incident (5.2)"))
        rules.append("5.2 P1: the duty manager must also approve, two different people")
    elif freeze:
        out.append(Approver(role="duty_manager", team=dm["team"], engineer=dm["engineer"],
                            why="change freeze, tier 1 (5.3)"))
        rules.append("5.3 change freeze (Fri 18:00 to Mon 06:00) and a tier-1 service: the duty manager also approves, with a written reason")
    if freeze and inc_sev == "P1":
        rules.append("5.3 change freeze also applies")
    return out, freeze, rules


def triage(alerts: list[Alert], cat: Catalog, id_start: int = 3001) -> list[Incident]:
    incidents: list[Incident] = []
    for n, group in enumerate(group_alerts(alerts, cat), start=id_start):
        services = sorted({a.service for a in group}, key=lambda s: min(t(a.time) for a in group if a.service == s))
        base = dict(
            incident_id=f"INC-{n}", opened=group[0].time, last_alert=group[-1].time,
            alert_ids=[a.alert_id for a in group], services=services,
        )
        rc = root_cause(group, cat)
        if rc is None:
            unknown = [s for s in services if not cat.known(s)]
            incidents.append(Incident(
                **base, root_cause=None, severity=None, status="NEEDS_PERSON", flags=["unknown service"],
                needs_person_reason=f"{', '.join(unknown)} is not in the service catalogue; the tower will not guess (3.3)",
                rules_applied=["3.3 an alert names a service that is not in the catalogue: NEEDS_PERSON, nothing else happens"]))
            continue
        flapping = is_flapping(group)
        sev, rules = severity_of(group, cat, rc)
        rules = [f"3.1/3.2 {len(group)} alert(s) from {len(services)} service(s) are one incident; root cause {rc}"] + rules
        sim = similar_incident(group, rc, "P4" if flapping else sev, cat)
        if sim:
            rules.append(f"6.1 similar past incident {sim}")
        if flapping:
            incidents.append(Incident(
                **base, root_cause=rc, severity="P4", status="AUTO_RESOLVED", flags=["flapping"],
                runbook_id=runbook_hint(rc, group[0].check, cat), similar_incident=sim,
                rules_applied=[f"3.1 {len(group)} alerts for {rc} within 15 minutes are one incident",
                               "2.5 every alert cleared by itself within 15 minutes: P4",
                               "3.4 all alerts cleared by themselves: AUTO_RESOLVED, nothing to do"]
                + ([f"6.1 similar past incident {sim}"] if sim else [])))
            continue
        approvers, freeze, arules = approvers_for(sev, rc, t(group[0].time), cat)
        flags = ["change freeze"] if freeze else []
        incidents.append(Incident(
            **base, root_cause=rc, severity=sev, status="WAITING_FOR_APPROVAL", target=rc,
            runbook_id=runbook_hint(rc, next((a.check for a in group if a.service == rc), group[0].check), cat),
            approvals_needed=len(approvers), approvers=approvers, freeze=freeze, similar_incident=sim,
            flags=flags, rules_applied=rules + arules))
    return incidents
