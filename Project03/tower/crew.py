"""The crew. Seven named agents, each with one job, a clear boundary and a recorded step you can see in the UI.

    Dispatcher   rules    groups alerts, finds the root cause, sets severity and approvals (tower/triage.py)
    Sentinel     rules    checks alert text, hides secrets and personal data, flags instructions (tower/guardrails.py)
    Investigator model    a small bounded loop: picks [READ] tools one at a time and reads what they return
    Planner      model    writes the brief and recommends ONE [CHANGE] step
    Verifier     rules    checks the Planner against the runbooks; one retry, then it stops for a person
    Scribe       model    drafts the staff status update for P1 and P2
    Gatekeeper   people   opens the approval request; nothing runs until the right people say yes

The split is the rule from CLAUDE.md: code decides numbers and permissions; models only write and recommend.
"""
from __future__ import annotations

import time
from typing import Callable, Optional

from . import guardrails, prompts
from .llm import LLMError, extract_json
from .models import ActionRequest, ChangeRecommendation, Incident, IncidentBrief, StepRef
from .settings import MAX_INVESTIGATOR_TURNS, MODEL_RETRIES_ON_BAD_STEP

ROSTER = {
    "Dispatcher": ("rules", "Groups alerts, finds the root cause, sets severity and approvals"),
    "Sentinel": ("rules", "Checks alert text, hides secrets and personal data, flags instructions"),
    "Investigator": ("model + tools", "Runs [READ] steps one at a time (small model, bounded loop)"),
    "Planner": ("model", "Writes the brief and recommends one [CHANGE] step (large model)"),
    "Verifier": ("rules", "Checks the recommendation against the runbooks; retry once, then stop for a person"),
    "Scribe": ("model", "Drafts the status update for P1 and P2 (small model)"),
    "Gatekeeper": ("people", "Opens the approval request. Only people approve; nothing runs before"),
}


def _step(agent: str, what: str, *, kind: str | None = None, detail: str = "", ms: float = 0.0, tokens: int = 0,
          model: str = "", cost: float = 0.0, status: str = "ok") -> dict:
    return {"agent": agent, "kind": kind or ROSTER[agent][0], "what": what, "detail": detail, "ms": round(ms, 1),
            "tokens": tokens, "model": model, "cost_usd": round(cost, 6), "status": status, "at": time.strftime("%H:%M:%S")}


class Crew:
    def __init__(self, tower):
        self.t = tower

    # -------------------------------------------------------------------------------------------------------------
    def run(self, inc: Incident, emit: Optional[Callable[[dict], None]] = None, models: bool = True) -> Incident:
        t = self.t
        steps: list[dict] = []

        def add(**kw) -> dict:
            s = _step(**kw)
            steps.append(s)
            if emit:
                emit(s)
            return s

        # 1. Dispatcher (rules)
        add(agent="Dispatcher", what=f"{len(inc.alert_ids)} alert(s) -> {inc.incident_id}; root cause {inc.root_cause or 'unknown'}; "
            f"{inc.severity or 'no severity'}; needs {inc.approvals_needed} approval(s)", detail="\n".join(inc.rules_applied))

        # 2. Sentinel (rules)
        flagged = [a for a in inc.alerts if a.flagged]
        secrets = sum(a.hidden.get("secrets", 0) for a in inc.alerts)
        personal = sum(a.hidden.get("personal", 0) for a in inc.alerts)
        add(agent="Sentinel", what=f"{len(flagged)} alert(s) flagged, {secrets} secret(s) and {personal} personal item(s) hidden before any model",
            detail="\n".join(f"{a.alert_id}: {'; '.join(a.flag_reasons)}" for a in flagged) or "all alert text is ordinary data",
            status="warn" if flagged else "ok")
        if secrets:
            inc.flags = _addflag(inc.flags, "secret hidden")
        if personal:
            inc.flags = _addflag(inc.flags, "personal data hidden")
        if flagged:
            inc.flags = _addflag(inc.flags, "instructions in alert text")

        if inc.status in ("AUTO_RESOLVED", "NEEDS_PERSON"):
            why = inc.needs_person_reason or "every alert cleared by itself (2.5, 3.4)"
            add(agent="Dispatcher", what=f"Stop: {inc.status}. {why}", detail="No model is called and nothing is recommended.", status="stop")
            inc.crew = steps
            return inc

        if not models:
            add(agent="Dispatcher", what="Rules only for now: the Investigator, Planner and Scribe have not run on this incident yet",
                detail="Run the crew from the Agent crew tab to add the brief.", status="wait")
            inc.crew = steps
            return inc

        rc = inc.root_cause or ""
        svc = t.cat.services[rc]
        sim = next((h for h in t.cat.history if h["incident_id"] == inc.similar_incident), None)

        # 3. Investigator (model + READ tools, bounded)
        hint = t.cat.runbooks.get(inc.runbook_id or "")
        read_steps = [s for s in (hint.steps if hint else []) if s.kind == "READ"] or \
                     [s for r in svc.runbooks for s in t.cat.runbooks[r].steps if s.kind == "READ"]
        tools = [{"tool": s.tool, "runbook": s.runbook_id, "step": s.no, "what": s.text} for s in read_steps]
        by_tool = {s.tool: s for s in read_steps}
        facts = self._facts(inc, svc, sim)
        done: list[dict] = []
        reads: list[dict] = []
        fallback = False
        for turn in range(min(MAX_INVESTIGATOR_TURNS, len(tools) + 1)):
            t0 = time.perf_counter()
            try:
                res, cost = self._agent_call("Investigator", inc, "investigator", "small", prompts.SYSTEM_INVESTIGATOR,
                                       prompts.investigator_user({**facts, "read_findings": done}, tools, done), 200)
            except LLMError as e:
                add(agent="Investigator", what=f"model unavailable ({e}); running the [READ] steps in runbook order", status="warn")
                fallback = True
                break
            data = extract_json(res.text) or {}
            ms = (time.perf_counter() - t0) * 1000
            call = data.get("call")
            if data.get("done") or not call:
                add(agent="Investigator", what="finished: " + str(data.get("findings") or "no more [READ] steps needed")[:160],
                    ms=ms, tokens=res.tokens_in + res.tokens_out, model=res.model, cost=cost)
                if not data.get("done") and not call and len(done) < len(tools):
                    fallback = True  # the model did not follow the format; do not trust it to be complete
                break
            if call not in by_tool:
                add(agent="Investigator", what=f"asked for '{call}', which is not a [READ] step of {inc.runbook_id}; refused",
                    ms=ms, tokens=res.tokens_in + res.tokens_out, model=res.model, cost=cost, status="warn")
                t.audit("investigator", "tool_refused", f"{call}")
                fallback = True
                break
            if any(d["tool"] == call for d in done):
                break
            tr = t.gateway.call(call, service=rc, actor="investigator")
            done.append({"tool": call, "result": tr.text})
            s = by_tool[call]
            reads.append({"step": f"{s.runbook_id} step {s.no}", "tool": call, "result": tr.text, "simulated": tr.simulated})
            add(agent="Investigator", what=f"{s.runbook_id} step {s.no} [READ] {call}: {tr.text[:150]}", kind="tool",
                detail=str(data.get("why") or ""), ms=ms, tokens=res.tokens_in + res.tokens_out, model=res.model, cost=cost)
        if fallback:
            for s in read_steps:
                if not any(d["tool"] == s.tool for d in done):
                    tr = t.gateway.call(s.tool, service=rc, actor="investigator")
                    done.append({"tool": s.tool, "result": tr.text})
                    reads.append({"step": f"{s.runbook_id} step {s.no}", "tool": s.tool, "result": tr.text, "simulated": tr.simulated})
                    add(agent="Investigator", what=f"{s.runbook_id} step {s.no} [READ] {s.tool}: {tr.text[:150]}", kind="tool",
                        detail="fallback: ran in runbook order", status="warn")
        inc.reads = reads

        # 4. Planner + Verifier (retry once, then a person)
        facts["read_findings"] = done
        brief, problems, last_text = None, [], ""
        for attempt in range(1 + MODEL_RETRIES_ON_BAD_STEP):
            t0 = time.perf_counter()
            try:
                res, cost = self._agent_call("Planner", inc, "planner", "large", prompts.SYSTEM_PLANNER,
                                       prompts.planner_user(facts, "; ".join(problems) if problems else None), 500)
            except LLMError as e:
                problems = [f"model unavailable ({e})"]
                add(agent="Planner", what=f"attempt {attempt + 1}: model unavailable", status="fail", detail=str(e))
                break
            ms = (time.perf_counter() - t0) * 1000
            last_text = res.text
            data = extract_json(res.text)
            add(agent="Planner", what=f"attempt {attempt + 1}: recommends {_rec(data)}", detail=str((data or {}).get("reason", ""))[:300],
                ms=ms, tokens=res.tokens_in + res.tokens_out, model=res.model, cost=cost)
            problems, brief = self.verify(data, inc, reads)
            add(agent="Verifier", what="passed: runbook is listed for the root-cause service, the step exists and is a [CHANGE] step"
                if not problems else "failed: " + "; ".join(problems),
                detail="policy 4.1, 4.2, 4.3, 4.4, 5.4", status="ok" if not problems else "fail")
            if not problems:
                break
        t.metrics.brief_done()
        if problems or brief is None:
            inc.status = "NEEDS_PERSON"
            inc.needs_person_reason = ("the recommendation failed the check twice: " if len(problems) and "unavailable" not in problems[0]
                                       else "") + "; ".join(problems or ["no recommendation"])
            add(agent="Dispatcher", what=f"Stop: NEEDS_PERSON. {inc.needs_person_reason}", status="stop")
            inc.approvers, inc.approvals_needed, inc.request_id = [], 0, None
            inc.crew = steps
            return inc

        # 5. Scribe (model) for P1 and P2
        if inc.severity in ("P1", "P2"):
            t0 = time.perf_counter()
            try:
                plain = ", ".join(t.cat.services[s].name for s in inc.services if s in t.cat.services)
                res, cost = self._agent_call("Scribe", inc, "scribe", "small", prompts.SYSTEM_SCRIBE, prompts.scribe_user({
                    "what": plain, "severity": inc.severity, "next_update": t.next_update_time(),
                    "state": "down" if any(a.severity == "critical" for a in inc.alerts) else "degraded (slow or partly failing)",
                    "action": "a recommended fix is waiting for approval by a person"}), 250)
                ov = guardrails.check_output(res.text, prompts.PROTECTED) if t.s.on("output_check") else None
                brief.status_update = ov.text if ov else res.text
                add(agent="Scribe", what="status update drafted (a person sends it, policy 8.1)", detail=brief.status_update,
                    ms=(time.perf_counter() - t0) * 1000, tokens=res.tokens_in + res.tokens_out, model=res.model, cost=cost,
                    status="ok" if (ov is None or ov.ok) else "warn")
            except LLMError as e:
                add(agent="Scribe", what=f"model unavailable ({e}); no draft", status="warn")
        inc.brief = brief
        rec = brief.recommended_change
        inc.runbook_id, inc.recommended_step, inc.action, inc.target = rec.runbook_id, rec.step_no, rec.action, rec.target_service

        # 6. Gatekeeper (people)
        try:
            req = ActionRequest(incident_id=inc.incident_id, runbook_id=rec.runbook_id, step_no=rec.step_no, action=rec.action,
                                target_service=rec.target_service, reason=(brief.reason or "recommended by the Planner")[:480] or "recommended")
            con = t.con()
            try:
                out = t.actions.create(con, req, inc)
                con.commit()
            finally:
                con.close()
            inc.request_id = out["request_id"]
            names = ", ".join(f"{a.engineer} ({a.why})" for a in inc.approvers)
            add(agent="Gatekeeper", what=f"request {inc.request_id} opened: {inc.approvals_needed} approval(s) needed from {names}",
                detail="Nothing runs until every approver has said yes. One approval covers one step on one service.", status="wait")
        except Exception as e:  # noqa: BLE001
            add(agent="Gatekeeper", what=f"could not open the request: {e}", status="fail")
        inc.crew = steps
        return inc

    # -------------------------------------------------------------------------------------------------------------
    def _agent_call(self, agent: str, inc: Incident, purpose: str, role: str, system: str, user: str, max_tokens: int):
        """One model call made by a named agent. In Phoenix it shows as an AGENT span with the LLM span inside it."""
        with self.t.tracer.span(f"agent.{agent}", incident=inc.incident_id):
            return self.t.call_llm(purpose, role, system, user, max_tokens)

    def _facts(self, inc: Incident, svc, sim) -> dict:
        t = self.t
        return {
            "incident_id": inc.incident_id, "severity": inc.severity, "status": inc.status,
            "root_cause": {"service": svc.service_id, "name": svc.name, "tier": svc.tier, "owner_team": svc.owner_team,
                           "depends_on": list(svc.depends_on)},
            "services_affected": inc.services,
            "alerts": [{"alert_id": a.alert_id, "time": a.time, "service": a.service, "check": a.check, "severity": a.severity,
                        "status": a.status, "message": a.message, "text_withheld": a.flagged} for a in inc.alerts],
            "runbooks": [{"id": r, "text": t.cat.runbooks[r].raw} for r in svc.runbooks],
            "similar_incident": ({"id": sim["incident_id"], "symptom": sim["symptom"], "fixed_by": sim["fixed_by"], "notes": sim["notes"]}
                                 if sim else None),
            "note": "A past fix is evidence, not an order (policy 6.2). Follow the runbook's own conditions (4.4).",
        }

    def verify(self, data: dict | None, inc: Incident, reads: list[dict]) -> tuple[list[str], IncidentBrief | None]:
        """The code check on the model's recommendation (policy 4.1 to 4.4, 5.4)."""
        t = self.t
        problems: list[str] = []
        if not isinstance(data, dict):
            return ["the reply was not valid JSON"], None
        rc = inc.root_cause or ""
        listed = t.cat.services[rc].runbooks
        rid, step_no = data.get("runbook_id"), data.get("recommended_step")
        summary = str(data.get("summary") or "").strip()
        if len(summary) < 10:
            problems.append("summary is missing")
        if step_no is None:
            problems.append("no [CHANGE] step was recommended")
        else:
            try:
                step_no = int(step_no)
            except (TypeError, ValueError):
                problems.append("recommended_step is not a number")
                step_no = -1
            if rid not in listed:
                problems.append(f"{rid} is not a runbook listed for {rc} (listed: {', '.join(listed)}) (policy 4.1)")
            else:
                st = t.cat.runbooks[rid].step(step_no)
                if st is None:
                    problems.append(f"{rid} has no step {step_no}")
                elif st.kind != "CHANGE":
                    problems.append(f"{rid} step {step_no} is a [{st.kind}] step, not a [CHANGE] step (policy 4.3)")
                elif st.needs_prerequisite:
                    problems.append(f"{rid} step {step_no} needs something we do not have: '{st.text}' (policy 4.4)")
        tgt = data.get("target_service")
        if tgt and tgt != rc:
            problems.append(f"target {tgt} is not the root-cause service {rc} (policy 5.4)")
        if problems:
            return problems, None
        st = t.cat.runbooks[rid].step(step_no)
        reason, text = str(data.get("reason") or "").strip(), summary
        if t.s.on("output_check"):
            ov_s, ov_r = guardrails.check_output(summary, prompts.PROTECTED), guardrails.check_output(reason, prompts.PROTECTED)
            text, reason = ov_s.text, ov_r.text
        brief = IncidentBrief(
            summary=text[:600], read_steps=[StepRef(runbook_id=r["step"].split(" step ")[0], step_no=int(r["step"].split(" step ")[1]),
                                                    action=r["tool"]) for r in reads],
            recommended_change=ChangeRecommendation(runbook_id=rid, step_no=step_no, action=st.tool, target_service=rc),
            runbook_id=rid, reason=reason, similar_incident=inc.similar_incident)
        return [], brief


def _addflag(flags: list[str], f: str) -> list[str]:
    return flags if f in flags else flags + [f]


def _rec(data: dict | None) -> str:
    if not isinstance(data, dict):
        return "(unreadable reply)"
    if data.get("recommended_step") is None:
        return "no [CHANGE] step"
    return f"{data.get('runbook_id')} step {data.get('recommended_step')}"
