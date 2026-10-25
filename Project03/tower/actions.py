"""Changes behind approval. An ActionRequest names one runbook step on one service. It runs only after the last required approver
says yes, writes one line to the actions log, and does so once, even if approved again (policy 1.2, 5.1 to 5.5).

[CHANGE] actions here are simulated: the "action" is a line in logs/actions.log. Nothing real is changed."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from threading import Lock

from . import db, guardrails
from .catalog import Catalog
from .models import ActionRequest, ApprovalIn, Incident
from .settings import Settings

_log_lock = Lock()


class ActionError(Exception):
    """A readable refusal. `code` maps to an HTTP status in the API."""

    def __init__(self, msg: str, code: int = 400):
        super().__init__(msg)
        self.code = code


def request_id_for(req: ActionRequest) -> str:
    return f"AR-{req.incident_id}-{req.runbook_id}-{req.step_no}"


class Actions:
    def __init__(self, s: Settings, cat: Catalog, clock):
        self.s = s
        self.cat = cat
        self.clock = clock  # callable returning the tower's current time string

    # ---- audit ----
    def audit(self, con, actor: str, event: str, detail: str) -> None:
        con.execute("INSERT INTO audit(ts, actor, event, detail) VALUES(?,?,?,?)",
                    (self.clock(), actor, event, guardrails.scrub(detail)[:500]))

    # ---- create ----
    def create(self, con, req: ActionRequest, inc: Incident) -> dict:
        rid = request_id_for(req)
        if req.target_service != inc.root_cause:
            raise ActionError(f"the request targets {req.target_service} but the root cause is {inc.root_cause}; "
                              "one approval covers one step on one service (policy 5.4)")
        svc = self.cat.services.get(req.target_service)
        if svc is None or req.runbook_id not in svc.runbooks:
            raise ActionError(f"{req.runbook_id} is not a runbook listed for {req.target_service} (policy 4.1)")
        step = self.cat.runbooks[req.runbook_id].step(req.step_no)
        if step is None or step.kind != "CHANGE":
            raise ActionError(f"{req.runbook_id} step {req.step_no} is not a [CHANGE] step")
        if step.tool != req.action:
            raise ActionError(f"the step runs {step.tool}, not {req.action}")
        existing = con.execute("SELECT * FROM action_requests WHERE request_id=?", (rid,)).fetchone()
        if existing and existing["status"] != "SUPERSEDED":
            return self.get(con, rid)
        if inc.status not in ("WAITING_FOR_APPROVAL",):
            raise ActionError(f"{inc.incident_id} is {inc.status}; there is nothing to approve")
        if existing:  # a request replaced by newer alerts: start fresh
            con.execute("DELETE FROM approvals WHERE request_id=?", (rid,))
            con.execute("DELETE FROM action_requests WHERE request_id=?", (rid,))
        required = [a.model_dump() for a in inc.approvers]
        con.execute("INSERT INTO action_requests VALUES(?,?,?,?,?,?,?,?,?,?,NULL)",
                    (rid, req.incident_id, req.runbook_id, req.step_no, req.action, req.target_service, req.reason,
                     "PENDING", json.dumps(required), self.clock()))
        self.audit(con, "tower", "request_created", f"{rid}: {req.action} on {req.target_service}; needs {len(required)} approval(s)")
        if not self.s.approvals_on:  # red-team 'approvals off' run only: shows what the approval step stops
            self._execute(con, rid, req.action, req.target_service, "UNAPPROVED")
        return self.get(con, rid)

    # ---- approve / reject ----
    def decide(self, con, rid: str, body: ApprovalIn) -> dict:
        row = con.execute("SELECT * FROM action_requests WHERE request_id=?", (rid,)).fetchone()
        if row is None:
            raise ActionError("no such request", 404)
        inc_row = con.execute("SELECT data FROM incidents WHERE incident_id=?", (row["incident_id"],)).fetchone()
        inc = Incident.model_validate_json(inc_row["data"])
        if row["status"] == "CHANGE_DONE":
            return {**self.get(con, rid), "note": "already executed; nothing new was written", "executed_now": False}
        if row["status"] == "REJECTED":
            raise ActionError("this request was rejected", 409)
        required = json.loads(row["required"])
        name = body.approver.strip()
        slot = next((r for r in required if r["engineer"].lower() == name.lower()), None)
        if slot is None:
            raise ActionError(f"{name} is not an approver for this request "
                              f"(needed: {', '.join(r['engineer'] + ' (' + r['why'] + ')' for r in required)})", 403)
        if body.decision == "reject":
            con.execute("UPDATE action_requests SET status='REJECTED' WHERE request_id=?", (rid,))
            self._set_incident_status(con, row["incident_id"], "REJECTED")
            con.execute("INSERT OR REPLACE INTO approvals(request_id, approver, decision, reason, ts) VALUES(?,?,?,?,?)",
                        (rid, slot["engineer"], "reject", guardrails.scrub(body.reason), self.clock()))
            self.audit(con, slot["engineer"], "rejected", f"{rid}: {guardrails.scrub(body.reason)}")
            return {**self.get(con, rid), "executed_now": False}
        if inc.freeze and len(body.reason.strip()) < 10:
            raise ActionError("change freeze (policy 5.3): a written reason of at least 10 characters is required", 422)
        if con.execute("SELECT 1 FROM approvals WHERE request_id=? AND approver=? AND decision='approve'", (rid, slot["engineer"])).fetchone():
            raise ActionError(f"{slot['engineer']} has already approved this request; two different people are needed", 409)
        con.execute("INSERT INTO approvals(request_id, approver, decision, reason, ts) VALUES(?,?,?,?,?)",
                    (rid, slot["engineer"], "approve", guardrails.scrub(body.reason), self.clock()))
        self.audit(con, slot["engineer"], "approved", f"{rid} ({slot['why']}) {guardrails.scrub(body.reason)}")
        done = {r["approver"] for r in con.execute("SELECT approver FROM approvals WHERE request_id=? AND decision='approve'", (rid,))}
        if all(r["engineer"] in done for r in required) and len(done) >= len(required):
            self._execute(con, rid, row["action"], row["target_service"], ", ".join(sorted(done)))
            return {**self.get(con, rid), "executed_now": True}
        return {**self.get(con, rid), "executed_now": False}

    def decide_safely(self, rid: str, body: ApprovalIn) -> dict:
        """One transaction: two approvals arriving together cannot both execute the action."""
        con = db.connect(self.s.db_path)
        try:
            with db.tx(con):
                return self.decide(con, rid, body)
        finally:
            con.close()

    # ---- execute (the only place a [CHANGE] step "runs") ----
    def _execute(self, con, rid: str, action: str, target: str, approved_by: str) -> None:
        line = f"{self.clock()} | {rid} | {action} on {target} | simulated | approved by: {approved_by}"
        path = Path(self.s.actions_log)
        path.parent.mkdir(parents=True, exist_ok=True)
        with _log_lock, open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        con.execute("UPDATE action_requests SET status='CHANGE_DONE', executed=? WHERE request_id=?", (self.clock(), rid))
        inc_id = con.execute("SELECT incident_id FROM action_requests WHERE request_id=?", (rid,)).fetchone()["incident_id"]
        self._set_incident_status(con, inc_id, "CHANGE_DONE")
        self.audit(con, "tower", "action_executed", line)

    def _set_incident_status(self, con, inc_id: str, status: str) -> None:
        row = con.execute("SELECT data FROM incidents WHERE incident_id=?", (inc_id,)).fetchone()
        if row:
            inc = Incident.model_validate_json(row["data"])
            inc.status = status  # type: ignore[assignment]
            con.execute("UPDATE incidents SET status=?, data=?, updated=? WHERE incident_id=?",
                        (status, inc.model_dump_json(), self.clock(), inc_id))

    # ---- read ----
    def get(self, con, rid: str) -> dict:
        row = con.execute("SELECT * FROM action_requests WHERE request_id=?", (rid,)).fetchone()
        if row is None:
            raise ActionError("no such request", 404)
        approvals = [dict(r) for r in con.execute(
            "SELECT approver, decision, reason, ts FROM approvals WHERE request_id=? ORDER BY id", (rid,))]
        d = dict(row)
        d["required"] = json.loads(d["required"])
        d["approvals"] = approvals
        done = {a["approver"] for a in approvals if a["decision"] == "approve"}
        d["waiting_for"] = [r["engineer"] for r in d["required"] if r["engineer"] not in done] if d["status"] == "PENDING" else []
        return d


def actions_log_lines(path: Path) -> list[str]:
    p = Path(path)
    return p.read_text(encoding="utf-8").splitlines() if p.exists() else []
