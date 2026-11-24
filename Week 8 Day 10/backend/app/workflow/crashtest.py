"""Homework: the crash test (done). 20 KYC exceptions run as case workflows, as Helen Achebe, with a crash armed at one point in
each, and then every case is scored from the bank's own records (score_case, homework Task 1).

The harness plays the people around the workflows: it decides each approval as the plan says (approve, reject, or let it
expire), and it makes each applicant reply the planned number of days after the bank asked them. It arms one crash per case
(data/Day10_HW_Slide04_crash_plan.json); the worker dies there and npm run dev starts it again.

From backend/, with npm run dev running:  python -m scripts.run_crashes       (about 5 minutes with 20-second days)
Results: engagement/workflow/crashtest.json, shown on the Workflows screen (Crash test tab).
"""

import json
import time

from app import store
from app.agent import runs
from app.config import CRASH_PLAN_FILE_10, DAY_SECONDS
from app.integration import auth
from app.workflow import engine, service, steps
from app.workflow.scoring import score_case


def plan() -> dict:
    return json.loads(CRASH_PLAN_FILE_10.read_text(encoding="utf-8"))


def result_of(key: str, ticket_id: str, started_at: float) -> dict:
    """What one case left behind: its end, the bank's writes, the agent's runs per round, and its crashes."""
    ev = steps.events(key)
    end = next((e.get("end", "") for e in reversed(ev) if e["kind"] == "end"), "")
    # runs the agent finished: a crash can cut a run short (it stays "running"), and that one is not counted
    agent_runs = [r for r in runs.list_runs(1000) if r["id"].startswith(key + "-") and r["status"] != "running"]
    by_round: dict[str, int] = {}
    for r in agent_runs:
        rnd = r["id"][len(key) + 2:].split("-")[0]
        by_round[rnd] = by_round.get(rnd, 0) + 1
    crashes = [c for c in engine._read(engine.CRASH_LOG, []) if c["ticket"] == ticket_id and c["at"] >= started_at]
    return {"key": key, "ticket_id": ticket_id, "end": end, "counts": service.counts(service.effects(ticket_id, started_at)),
            "agent_runs": by_round, "crashes": [c["point"] for c in crashes]}


def run(progress=print, limit_s: float | None = None) -> dict:
    spec = plan()
    token = auth.sign_in_as(spec["run_as"])
    started = time.time()
    keys = {}
    for c in spec["cases"]:
        if c["crash"] != "none":
            engine.arm(c["crash"], c["ticket_id"])
        keys[c["ticket_id"]] = service.start_case(token, c["ticket_id"])
    progress(f"Started {len(keys)} case workflows as {spec['run_as']}; one crash armed in {sum(c['crash'] != 'none' for c in spec['cases'])} of them")
    by_ticket = {c["ticket_id"]: c for c in spec["cases"]}
    replied: set[str] = set()
    decided: set[str] = set()
    deadline = started + (limit_s or 30 * DAY_SECONDS + 240)
    while time.time() < deadline:
        token = auth.sign_in_as(spec["run_as"])  # a fresh token for the decisions (the workflows use their case grants)
        # the people: decide approvals as planned
        for a in runs.approvals():
            if a["status"] != "pending" or a["id"] in decided or not a.get("workflow_id", "").startswith("case-"):
                continue
            t = a["ticket_id"]
            if t not in keys or not a["workflow_id"] == keys[t]:
                continue
            d = by_ticket[t]["decision"]
            rnd = 2 if "-r2-" in a["run_id"] else 1
            if d == "expire":
                continue
            approve = not (d == "reject" or (d == "reject_round2" and rnd == 2))
            try:
                service.decide(a["id"], approve, spec["run_as"], "" if approve else "Crash test: rejected as planned")
                decided.add(a["id"])
            except (ValueError, PermissionError):
                decided.add(a["id"])
        # the applicants: reply as planned, counted from the bank's first request
        for t, c in by_ticket.items():
            if t in replied or c["reply_after_days"] is None:
                continue
            msgs = [m for m in service.effects(t, started)["messages"] if m["kind"] == "request"]
            if msgs and time.time() >= msgs[0]["t"] + c["reply_after_days"] * DAY_SECONDS:
                service.applicant_reply(t, c["doc_type"])
                replied.add(t)
                progress(f"{t}: the applicant replied (day {c['reply_after_days']})")
        ended = {t: any(e["kind"] == "end" for e in steps.events(k)) for t, k in keys.items()}
        if all(ended.values()):
            break
        time.sleep(0.5)
    results = []
    for c in spec["cases"]:
        r = result_of(keys[c["ticket_id"]], c["ticket_id"], started)
        try:
            s = score_case(r, c)
        except NotImplementedError as e:
            s = {"checks": {}, "passed": None, "error": str(e)}
        results.append({**c, **r, "score": s})
        progress(f"{c['id']} {c['ticket_id']}: {r['end'] or 'not ended'} · crash {c['crash']}"
                 f"{' (fired)' if r['crashes'] else (' (did not fire)' if c['crash'] != 'none' else '')} -> "
                 f"{'pass' if s.get('passed') else ('not scored' if s.get('passed') is None else 'FAIL ' + ', '.join(k for k, v in s['checks'].items() if not v))}")
    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "run_as": spec["run_as"], "day_seconds": DAY_SECONDS,
           "seconds": round(time.time() - started), "scored": all(x["score"].get("passed") is not None for x in results),
           "passed": sum(1 for x in results if x["score"].get("passed")), "total": len(results),
           "crashes_fired": sum(1 for x in results if x["crashes"]), "results": results}
    store.save("workflow/crashtest.json", out)
    return out


def state() -> dict:
    return store.load("workflow/crashtest.json", {"results": [], "passed": 0, "total": len(plan()["cases"]), "at": None})
