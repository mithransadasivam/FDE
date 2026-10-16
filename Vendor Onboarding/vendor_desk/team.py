"""The team (Phases 8-10): a supervisor, specialists, a reviewer and an approval gate, as one LangGraph.

    entry -> supervisor -> intake / documents / finance / compliance / reviewer / followup -> supervisor -> ... -> finalize
    finalize -> gate (a person decides; the graph is paused in a SQLite checkpoint) -> create (the one write) -> END

The supervisor's routing is a short rule in plain code (`route`), with a step limit and a revision limit. The reviewer is
plain code too: it re-derives every check from the tool evidence and sends any specialist's work back if it does not match.
The recommended decision is derived from verified evidence under policy §7, never from a model's say-so. Nothing is
written unless a person approves: only `create` writes, only after the right number of different approvers, once per case.
"""
import json
import operator
from typing import Annotated, Optional, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from vendor_desk import audit, casestore, config, decision, documents, rules
from vendor_desk.contracts import Assessment, ReviewVerdict
from vendor_desk.followup import check_draft, custom_followup
from vendor_desk.notes import case_id_for
from vendor_desk.specialists import run_specialist
from vendor_desk.states import IllegalMove, RetryBudget, State
from vendor_desk.tools import BackendDown

ROLES = ("documents", "finance", "compliance")
FAILURE_LABEL = {"handoff_failed": "handoff failed", "tool_error_limit": "tool errors", "step_limit": "step limit",
                 "llm_error": "model unreachable", "backend_down": "tool server unreachable"}


def _count(old, new):
    """Counter reducer: adds, and a None resets to zero (a person's re-run starts with a clean budget)."""
    return 0 if new is None else (old or 0) + new


class TeamState(TypedDict, total=False):
    case_id: str
    mode: str                       # new | reply | rerun
    reply_id: str                   # the vendor reply that resumes a case
    person: str                     # who restarted a stopped case
    thread: list
    new_ids: list                   # messages intake has not read yet
    request: Optional[dict]
    documents: Optional[dict]
    compliance: Optional[dict]
    finance: Optional[dict]
    review: Optional[dict]
    followup: Optional[dict]
    feedback: dict                  # role -> what the reviewer wants fixed
    revisions: int
    steps: int
    stop_reason: Optional[str]
    next: list
    gate: str
    tool_errors: Annotated[int, _count]
    handoff_failures: Annotated[int, _count]
    log: Annotated[list, operator.add]


# ---------------------------------------------------------------------------------------------- the routing rule
def route(s: dict, parallel: bool = False) -> list[str]:
    """The supervisor's whole decision, as a short rule. Returns the node(s) to run next."""
    if s.get("stop_reason"):
        return ["finalize"]
    if s.get("new_ids") or not s.get("request"):
        return ["intake"]
    todo = [r for r in ("documents", "finance") if s.get(r) is None]
    if todo:
        return todo if parallel else todo[:1]      # documents and finance do not depend on each other
    if s.get("compliance") is None:                # compliance needs the legal name and tax ID from documents
        return ["compliance"]
    if s.get("review") is None:
        return ["reviewer"]
    if s["review"]["verdict"] == "approve" and s["review"]["decision"] == "waiting for vendor" and s.get("followup") is None:
        return ["followup"]
    return ["finalize"]


def candidates(s: dict) -> list[str]:
    """Every node that could legally run next. The rule picks one of them; a model supervisor (stretch goal) may pick
    instead, but only from this list, and anything else falls back to the rule."""
    if s.get("stop_reason") or s.get("new_ids") or not s.get("request"):
        return route(s)
    pending = [r for r in ("documents", "finance") if s.get(r) is None]
    if s.get("compliance") is None and s.get("documents") is not None:
        pending.append("compliance")
    return pending or route(s)


SUPERVISOR_PROMPT = """ROLE: supervisor
You route a supplier onboarding case between specialists. Reply with exactly ONE name from the list of options and nothing
else. You cannot add steps, skip the reviewer or approve anything; code checks your answer against the allowed options."""


# ---------------------------------------------------------------------------------------------- the writers
class LocalWriter:
    """Creates the vendor by calling the same function the MCP server uses (for tests and local mode)."""

    def __init__(self, db_path=None):
        self.db_path = db_path

    def create(self, case_id, request_ids, approvers, approvals_required, payment_terms_days) -> dict:
        from vendor_desk.mcp_server import create_vendor_from_documents
        try:
            return create_vendor_from_documents(case_id, request_ids, approvers, approvals_required,
                                                payment_terms_days, db_path=self.db_path)
        except documents.ToolProblem as err:
            return {"error": str(err)}


class McpWriter:
    """Starts a server with writes switched ON for this one call, calls create_vendor, and shuts it down again."""

    def create(self, case_id, request_ids, approvers, approvals_required, payment_terms_days) -> dict:
        from vendor_desk.mcp_client import McpBackend
        backend = McpBackend(writes=True)
        try:
            return backend.call("create_vendor", {
                "case_id": case_id, "request_ids": request_ids, "approvers": approvers,
                "approvals_required": approvals_required, "payment_terms_days": payment_terms_days})
        finally:
            backend.close()


# ---------------------------------------------------------------------------------------------- the team
class Team:
    def __init__(self, llm, backend, writer, checkpointer, parallel: bool = False, supervisor_mode: str = "rule"):
        self.llm, self.backend, self.writer, self.parallel = llm, backend, writer, parallel
        self.supervisor_mode = supervisor_mode
        self.graph = self._build(checkpointer)

    # ------------------------------------------------------------------ graph wiring
    def _build(self, checkpointer):
        g = StateGraph(TeamState)
        g.add_node("entry", self.entry)
        g.add_node("supervisor", self.supervisor)
        for role in ("intake", "documents", "compliance", "finance", "followup"):
            g.add_node(role, self._specialist(role))
        g.add_node("reviewer", self.reviewer)
        g.add_node("finalize", self.finalize)
        g.add_node("gate", self.gate)
        g.add_node("create", self.create)
        g.add_edge(START, "entry")
        g.add_edge("entry", "supervisor")
        targets = ["intake", "documents", "compliance", "finance", "reviewer", "followup", "finalize"]
        g.add_conditional_edges("supervisor", lambda s: s["next"], targets)
        for node in ("intake", "documents", "compliance", "finance", "reviewer", "followup"):
            g.add_edge(node, "supervisor")
        g.add_conditional_edges("finalize", lambda s: "gate" if s.get("gate") == "wait" else END, ["gate", END])
        g.add_conditional_edges("gate", lambda s: {"again": "gate", "create": "create", "rerun": "entry"}.get(s.get("gate"), END),
                                ["gate", "create", "entry", END])
        g.add_edge("create", END)
        return g.compile(checkpointer=checkpointer)

    # ------------------------------------------------------------------ helpers
    def _log(self, case_id: str, who: str, event: str, detail: str, evidence: str = "") -> str:
        audit.append(case_id, who, event, detail, evidence)
        return f"{who}: {detail}"

    def _record_specialist(self, case_id: str, role: str, res, summary: str) -> None:
        """Audit the tool calls and the handoff, add the cost, and keep the raw tool evidence for the reviewer."""
        for tr in res.tool_results:
            r = tr["result"]
            audit.append(case_id, role, "tool_call", f"{tr['name']}({_short(tr['args'])})",
                         r.get("evidence") or r.get("error", ""))
        for e in res.trace:
            if e["type"] == "handoff_rejected":
                audit.append(case_id, role, "handoff_rejected", "report did not fit its contract; retrying once",
                             e["error"][:200])
        audit.append(case_id, role, "handoff", summary)

        def apply(case):
            casestore.add_usage(case, role, res.usage.as_dict())
            for tr in res.tool_results:
                r = tr["result"]
                if "error" not in r and r.get("check"):
                    case["raw"][r["check"]] = r
                if tr["name"] == "read_request" and "error" not in r and r.get("injection_scan", {}).get("suspicious"):
                    case["injection"] = True
                    scan = r["injection_scan"]
                    case["injection_detail"] = {"patterns": sorted(set(case.get("injection_detail", {}).get("patterns", []))
                                                                    | set(scan["patterns"])),
                                                "found_in": sorted(set(case.get("injection_detail", {}).get("found_in", []))
                                                                   | set(scan["found_in"]))}
        casestore.update(case_id, apply)

    # ------------------------------------------------------------------ nodes
    def entry(self, s: TeamState) -> dict:
        cid, mode = s["case_id"], s.get("mode", "new")
        case = casestore.load(cid)
        reset = {"steps": 0, "revisions": 0, "stop_reason": None, "next": [], "gate": "", "feedback": {}, "review": None,
                 "followup": None, "tool_errors": None, "handoff_failures": None}
        if mode == "new" and case is not None:
            raise ValueError(f"Case {cid} already exists; send a vendor reply or re-run it instead.")
        if mode == "new":
            first = documents.load_request(s["thread"][0])
            case = casestore.new_case(cid, s["thread"][0], first["subject"], first["from"], first["date"])
            casestore.save(case)
            audit.append(cid, "system", "request_received", f"{first['subject']} from {first['from']}", s["thread"][0])
            casestore.transition(case, State.RECEIVED, "request received")
            casestore.transition(case, State.CHECKING, "checks started")
            return {**reset, "new_ids": list(s["thread"]), "request": None, "documents": None, "compliance": None,
                    "finance": None, "log": [f"entry: case {cid} opened for {s['thread'][0]}"]}
        if mode == "reply":
            thread = list(case["request_ids"]) + [s["reply_id"]]
            case["request_ids"] = thread
            audit.append(cid, "system", "reply_received", f"vendor reply {s['reply_id']} resumes the case from its checkpoint",
                         s["reply_id"])
            casestore.transition(case, State.CHECKING, "vendor reply received")
            return {**reset, "thread": thread, "new_ids": [s["reply_id"]], "mode": "new",
                    "log": [f"entry: reply {s['reply_id']} resumes {cid}"]}
        # rerun: a person restarted a stopped case
        audit.append(cid, s.get("person", "a person"), "decision", "restarted the checks")
        casestore.transition(case, State.CHECKING, "a person restarted the checks", s.get("person", "a person"), True)
        case["raw"], case["injection"], case["stop_reason"] = {}, False, None
        casestore.save(case)
        return {**reset, "new_ids": list(case["request_ids"]), "request": None, "documents": None, "compliance": None,
                "finance": None, "mode": "new", "log": [f"entry: {cid} restarted by a person"]}

    def supervisor(self, s: TeamState) -> dict:
        steps = s.get("steps", 0) + 1
        update = {"steps": steps, "log": []}
        if steps > config.SUPERVISOR_STEP_LIMIT and not s.get("stop_reason"):
            update["stop_reason"] = f"Supervisor step limit of {config.SUPERVISOR_STEP_LIMIT} reached."
        state = {**s, **update}
        # bounded retries: tool errors and handoff failures stop the case (Phase 9)
        if not state.get("stop_reason"):
            budget = RetryBudget(handoff_limit=1, tool_error_limit=config.TOOL_ERROR_LIMIT)
            update["stop_reason"] = (budget.record("handoff", s.get("handoff_failures", 0)) if s.get("handoff_failures") else None)                 or (budget.record("tool_error", s.get("tool_errors", 0)) if s.get("tool_errors") else None)
            state["stop_reason"] = update["stop_reason"]
        nxt = route(state, self.parallel)
        note = ""
        options = candidates(state)
        if self.supervisor_mode == "model" and not state.get("stop_reason") and len(options) > 1:
            nxt, note = self._model_route(s["case_id"], state, options, nxt)
        update["next"] = nxt
        update["log"] = [f"supervisor -> {', '.join(nxt)}" + (" (in parallel)" if len(nxt) > 1 else "") + note]
        return update

    def _model_route(self, case_id: str, state: dict, options: list[str], rule_choice: list[str]):
        """A model picks the next specialist from the legal options; anything else falls back to the rule."""
        messages = [{"role": "system", "content": SUPERVISOR_PROMPT},
                    {"role": "user", "content": "Task: " + json.dumps({"options": options, "done": [
                        r for r in ("intake", "documents", "finance", "compliance") if state.get(r if r != "intake" else "request")]})}]
        try:
            reply = self.llm.chat(messages, tools=None, role="supervisor")
        except Exception as err:   # an unreachable model must not stop routing: the rule is the safety net
            return rule_choice, f" [model supervisor failed ({type(err).__name__}); rule used]"
        casestore.update(case_id, lambda c: casestore.add_usage(c, "supervisor", {
            "model_calls": 1, "tokens": reply.prompt_tokens + reply.completion_tokens, "seconds": reply.seconds}))
        choice = reply.content.strip().strip(".").lower()
        if choice in options:
            return [choice], " [chosen by the model]"
        audit.append(case_id, "supervisor", "refused", f"the model chose '{choice[:40]}', not one of {options}; rule used")
        return rule_choice, f" [model chose '{choice[:30]}', not allowed; rule used]"

    def _payload(self, role: str, s: TeamState, case: dict) -> dict:
        req, docs = s.get("request") or {}, s.get("documents") or {}
        thread = s["thread"]
        if role == "intake":
            return {"request_ids": s.get("new_ids") or thread}
        if role == "documents":
            return {"thread": thread}
        if role == "finance":
            return {"thread": thread, "terms_days": req.get("payment_terms_days"), "amount_gbp": req.get("amount_gbp"),
                    "period": req.get("period")}
        if role == "compliance":
            return {"vendor_name": docs.get("legal_name") or req.get("vendor_name"), "tax_id": docs.get("tax_id"),
                    "request_id": thread[-1]}
        a = _assessment_from_case(case, s)
        return {"assessment": {k: a[k] for k in ("vendor_name", "missing_items", "flags", "recommended_decision", "checks")},
                "requester": req.get("requester_email", "requester@example.com"), "request_id": thread[-1]}

    def _specialist(self, role: str):
        def node(s: TeamState) -> dict:
            cid = s["case_id"]
            case = casestore.load(cid)
            payload = self._payload(role, s, case)
            res = run_specialist(role, self.llm, self.backend, payload, feedback=(s.get("feedback") or {}).get(role))
            if role == "followup" and res.status == "ok":
                problems = check_draft(res.report, _assessment_from_case(case, s))
                if problems:   # a draft that breaks the rules goes back as a failed handoff
                    res.status, res.message = "handoff_failed", "follow-up draft rejected: " + "; ".join(problems)
            self._record_specialist(cid, role, res, f"{role} -> supervisor: {_report_name(role)} "
                                                    f"({res.status}, {res.usage.tool_calls} tool calls)")
            line = f"{role} -> supervisor: {_report_name(role)} {_describe(role, res.report)}"
            update = {"log": [line], "tool_errors": res.tool_errors}
            if res.status != "ok":
                update["stop_reason"] = f"{role} specialist stopped ({FAILURE_LABEL.get(res.status, res.status)}): {res.message}"
                update["handoff_failures"] = 1 if res.status == "handoff_failed" else 0
                update["log"] = [f"{role} -> supervisor: FAILED {res.status}: {res.message[:120]}"]
                return update
            if res.retried:
                update["log"].insert(0, f"{role}: first report was rejected at the boundary, retried once with the error")
            if role == "intake":
                update.update(self._after_intake(s, res.report))
                update["log"].append(update.pop("_note", ""))
            else:
                update[role] = res.report
            return update
        return node

    def _after_intake(self, s: TeamState, report: dict) -> dict:
        """Merge the new facts into the request; for a vendor reply, reset only what the reply affects."""
        old = s.get("request")
        merged = dict(report)
        out = {"new_ids": []}
        if old:
            for k in ("vendor_name", "requester_email"):
                merged[k] = old[k]
            for k in ("payment_terms_days", "amount_gbp", "period"):
                if merged.get(k) is None:
                    merged[k] = old.get(k)
            merged["attachment_types"] = sorted(set(old.get("attachment_types", [])) | set(report["attachment_types"]))
            merged["asks_to_skip_or_approve"] = old.get("asks_to_skip_or_approve") or report["asks_to_skip_or_approve"]
            types = set(report["attachment_types"])
            affected = set()
            if types:
                affected.add("documents")
                if types & {"bank_letter", "tax_registration"}:
                    affected.add("finance")
                if "tax_registration" in types:
                    affected.add("compliance")
            if report.get("payment_terms_days") is not None or report.get("amount_gbp") is not None:
                affected.add("finance")
            for role in affected:
                out[role] = None
            out["review"], out["followup"] = None, None
            out["_note"] = f"intake: reply affects {', '.join(sorted(affected)) or 'nothing new'}"
        else:
            out["_note"] = ""
        out["request"] = merged
        cid = s["case_id"]
        casestore.update(cid, lambda c: c.update(facts=merged) or c.update(
            injection=c["injection"] or merged["asks_to_skip_or_approve"], vendor_name=merged["vendor_name"]))
        return out

    # ------------------------------------------------------------------ the reviewer (plain code)
    def reviewer(self, s: TeamState) -> dict:
        cid = s["case_id"]
        case = casestore.load(cid)
        raw, issues, send_back, feedback = case["raw"], [], set(), {}

        def complain(role, text):
            issues.append(f"{role}: {text}")
            feedback.setdefault(role, []).append(text)
            send_back.add(role)

        def verify(role, check_result, check_name):
            tool_out = raw.get(check_name)
            if tool_out is None:
                complain(role, f"the {check_name} check was reported but no tool result supports it")
                return
            expected = decision.to_check_result(tool_out)
            for field, label in (("tool", "tool"), ("result", "result"), ("policy_section", "policy section")):
                if check_result[field] != expected[field]:
                    complain(role, f"the {check_name} {label} is '{check_result[field]}' but the evidence says "
                                   f"'{expected[field]}' ({tool_out['tool']}: {tool_out['evidence'][:90]})")
                    return

        if s.get("documents"):
            verify("documents", s["documents"]["check"], "documents")
            if sorted(s["documents"]["missing_items"]) != sorted(raw.get("documents", {}).get("missing", [])):
                complain("documents", "missing_items differ from what check_documents returned")
        if s.get("compliance"):
            verify("compliance", s["compliance"]["duplicate"], "duplicate")
            verify("compliance", s["compliance"]["watchlist"], "watchlist")
        if s.get("finance"):
            fin, req = s["finance"], s.get("request") or {}
            verify("finance", fin["bank"], "bank")
            for key, check_name, stated in (("payment_terms", "payment_terms", req.get("payment_terms_days")),
                                            ("spend", "spend", req.get("amount_gbp"))):
                if fin.get(key):
                    verify("finance", fin[key], check_name)
                elif stated is not None:
                    complain("finance", f"the request states {check_name.replace('_', ' ')} but that check is missing")
        for check in ("duplicate", "watchlist", "bank", "documents"):
            if check not in raw:
                complain({"duplicate": "compliance", "watchlist": "compliance", "bank": "finance",
                          "documents": "documents"}[check], f"the always-run {check} check has no evidence")
        if issues:
            revisions = s.get("revisions", 0) + 1
            verdict = ReviewVerdict(verdict="revise", issues=issues, send_back_to=sorted(send_back),
                                    notes="work sent back").model_dump()
            update = {"review": None, "feedback": feedback, "revisions": revisions,
                      "log": [f"reviewer -> supervisor: SENT BACK to {', '.join(sorted(send_back)) or 'intake'}: {issues[0][:150]}"]}
            for role in send_back:
                update[role] = None
            if revisions > config.REVISION_LIMIT:
                update["stop_reason"] = f"Revision limit of {config.REVISION_LIMIT} reached; the reviewer is still not satisfied."
            audit.append(cid, "reviewer", "verdict", f"revise ({', '.join(sorted(send_back))}): {issues[0]}"[:300])
            casestore.update(cid, lambda c: c.update(reviewer={**verdict, "revisions": revisions}))
            return update
        injection = bool(case["injection"])
        d = decision.derive(raw, injection)
        verdict = ReviewVerdict(verdict="approve", decision=d.decision, notes=(
            f"All {len(raw)} results match their tool evidence. Decision follows policy §7: {d.decision}.")).model_dump()
        audit.append(cid, "reviewer", "verdict", f"approve: {verdict['notes']}")
        casestore.update(cid, lambda c: c.update(reviewer={**verdict, "revisions": s.get("revisions", 0)}))
        return {"review": verdict, "feedback": {}, "log": [f"reviewer -> supervisor: approve ({d.decision})"]}

    # ------------------------------------------------------------------ finalize: set the status, wait for a person
    def finalize(self, s: TeamState) -> dict:
        cid = s["case_id"]
        case = casestore.load(cid)
        if s.get("stop_reason"):
            reason = s["stop_reason"]
            case["stop_reason"], case["next_step"] = reason, "stopped: " + reason[:110]
            casestore.save(case)
            if case["status"] != State.STOPPED.value:
                casestore.transition(case, State.STOPPED, reason)
            audit.append(cid, "system", "stopped", reason)
            return {"gate": "", "log": [f"finalize: STOPPED: {reason}"]}
        a = _assessment_from_case(case, s)
        d = a["recommended_decision"]

        def apply(c):
            c.update(assessment=a, decision=d, flags=a["flags"], missing_items=a["missing_items"], reasons=a["reasons"],
                     checks=a["checks"], approvers_required=a["approvers_required"],
                     annual_spend_gbp=a["annual_spend_gbp"], vendor_name=a["vendor_name"], stop_reason=None,
                     draft_email=s.get("followup") if d == "waiting for vendor" else None)
        case = casestore.update(cid, apply)
        audit.append(cid, "supervisor", "decision", f"recommended: {d}", "; ".join(a["reasons"])[:280])
        gate = ""
        if d == "waiting for vendor":
            reason = "waiting for the vendor: " + "; ".join(a["reasons"])[:150]
            casestore.transition(case, State.WAITING_FOR_VENDOR, reason)
            case["next_step"] = "draft follow-up ready; a person sends it, then the vendor's reply resumes this case"
        elif d == "ready for approval":
            casestore.transition(case, State.READY_FOR_APPROVAL, "every check passed")
            case["next_step"] = f"approver 1 of {a['approvers_required'] or 1}"
            gate = "wait"
        else:
            why = "; ".join(a["reasons"])[:200]
            label = "Recommended rejection (a person confirms)" if d == "reject" else "A person must look"
            case["stop_reason"] = f"{label}: {why}"
            casestore.transition(case, State.STOPPED, case["stop_reason"])
            case["next_step"] = ("a person must confirm the rejection: " if d == "reject" else "a person must look: ") + why[:110]
            gate = "wait"
        casestore.save(case)
        return {"gate": gate, "log": [f"finalize: {d} -> {case['status']}"]}

    # ------------------------------------------------------------------ the approval gate (a person)
    def gate(self, s: TeamState) -> dict:
        cid = s["case_id"]
        case = casestore.load(cid)
        allowed = allowed_actions(case)
        answer = interrupt({"case_id": cid, "status": case["status"], "decision": case["decision"],
                            "allowed_actions": allowed, "approvals": case["approvals"],
                            "approvers_required": case["approvers_required"]})
        # everything below runs only after a person has answered (the node restarts on resume)
        case = casestore.load(cid)
        person, action, comment = (answer.get("person") or "").strip(), answer.get("action"), answer.get("comment", "")
        allowed = allowed_actions(case)
        if not person:
            audit.append(cid, "system", "refused", f"{action}: no person named; a decision needs a named person")
            return {"gate": "again", "log": ["gate: refused, no person named"]}
        if action not in allowed:
            audit.append(cid, person, "refused", f"{action} is not allowed while the case is {case['status']}")
            return {"gate": "again", "log": [f"gate: {action} refused ({case['status']})"]}
        if action == "approve":
            if person.lower() in [a["approver"].lower() for a in case["approvals"]]:
                audit.append(cid, person, "refused", "the same person cannot approve twice (policy §6.4)")
                return {"gate": "again", "log": [f"gate: {person} cannot approve twice"]}
            case["approvals"].append({"approver": person, "at": casestore.now(), "comment": comment})
            need = case["approvers_required"] or 1
            audit.append(cid, person, "decision", f"approved ({len(case['approvals'])} of {need})", comment)
            if len(case["approvals"]) >= need:
                casestore.transition(case, State.APPROVED, f"{need} approval(s) from different people", person, True)
                return {"gate": "create", "log": [f"gate: approved by {len(case['approvals'])} -> create"]}
            case["next_step"] = f"approver {len(case['approvals']) + 1} of {need}"
            casestore.save(case)
            return {"gate": "again", "log": [f"gate: {person} approved, waiting for the next approver"]}
        if action == "reject":
            audit.append(cid, person, "decision", "rejected the vendor", comment)
            casestore.transition(case, State.REJECTED, comment or "rejected by a person", person, True)
            case["next_step"] = "closed by a person"
            casestore.save(case)
            return {"gate": "end", "log": [f"gate: rejected by {person}"]}
        if action == "ask_vendor":
            req = case["facts"] or {}
            draft = custom_followup(case["vendor_name"] or "the vendor", req.get("requester_email", "requester@example.com"),
                                    case["request_ids"][-1], comment or "Please confirm the details of your request.")
            case["draft_email"] = draft
            audit.append(cid, person, "decision", "asked the vendor for more information", comment)
            casestore.transition(case, State.WAITING_FOR_VENDOR, "a person asked the vendor: " + (comment or "more information"),
                                 person, True)
            case["next_step"] = "draft follow-up ready; waiting for the vendor"
            case["approvals"] = []
            casestore.save(case)
            return {"gate": "end", "log": [f"gate: {person} asked the vendor"]}
        if action == "release":
            audit.append(cid, person, "decision", "looked at the flags and released the case for approval", comment)
            case["approvals"] = []
            casestore.transition(case, State.READY_FOR_APPROVAL, "a person looked and released it: " + (comment or "ok"),
                                 person, True)
            case["next_step"] = f"approver 1 of {case['approvers_required'] or 1}"
            casestore.save(case)
            return {"gate": "again", "log": [f"gate: {person} released the case"]}
        return {"gate": "rerun", "mode": "rerun", "person": person, "log": [f"gate: {person} restarted the checks"]}

    # ------------------------------------------------------------------ the one write
    def create(self, s: TeamState) -> dict:
        cid = s["case_id"]
        case = casestore.load(cid)
        if case["vendor_id"] or case["status"] == State.CREATED.value:       # already done: never write twice
            audit.append(cid, "system", "write", f"skipped: vendor {case['vendor_id']} already created for this case")
            return {"log": ["create: already created, nothing written"]}
        if case["status"] != State.APPROVED.value:
            audit.append(cid, "system", "refused", f"create_vendor refused: the case is {case['status']}, not APPROVED")
            return {"log": ["create: refused, case not approved"]}
        req = case["facts"]
        approvers = [a["approver"] for a in case["approvals"]]
        audit.append(cid, "system", "write", "create_vendor requested through the MCP server (writes on for this call only)")
        try:
            result = self.writer.create(cid, case["request_ids"], approvers, case["approvers_required"] or 1,
                                        int(req.get("payment_terms_days") or 30))
        except BackendDown as err:
            result = {"error": str(err)}
        if "error" in result:
            casestore.transition(case, State.STOPPED, "vendor creation failed: " + result["error"][:150])
            case["stop_reason"] = "vendor creation failed: " + result["error"][:150]
            casestore.save(case)
            audit.append(cid, "system", "write", "create_vendor failed", result["error"])
            return {"log": ["create: FAILED " + result["error"][:100]]}
        case["vendor_id"] = result["vendor_id"]
        how = "new" if result["created"] else "already existed (idempotent: nothing written again)"
        casestore.transition(case, State.CREATED, f"vendor {result['vendor_id']} created ({how})")
        case["next_step"] = f"vendor {result['vendor_id']} created"
        casestore.save(case)
        audit.append(cid, "system", "write", f"create_vendor -> {result['vendor_id']}, keyed by case id", cid)
        return {"log": [f"create: {result['vendor_id']} ({how})"]}


# ---------------------------------------------------------------------------------------------- helpers
def allowed_actions(case: dict) -> list[str]:
    status = case["status"]
    if status == State.READY_FOR_APPROVAL.value:
        return ["approve", "reject", "ask_vendor"]
    if status == State.STOPPED.value:
        if case.get("decision") == "stop for a person":
            return ["release", "reject", "rerun"]
        return ["reject", "rerun"]
    if status == State.WAITING_FOR_VENDOR.value:
        return ["reject"]
    return []


def _assessment_from_case(case: dict, s: dict) -> dict:
    """Assemble the Assessment from the verified raw tool evidence (policy §7 applied by decision.derive)."""
    raw = case["raw"]
    d = decision.derive(raw, bool(case["injection"]))
    order = ["documents", "duplicate", "watchlist", "payment_terms", "bank", "spend"]
    docs = raw.get("documents", {})
    name = docs.get("legal_name") or (case.get("facts") or {}).get("vendor_name") or "Unknown supplier"
    request_id = (s.get("thread") or case["request_ids"])[-1]
    return Assessment(
        request_id=request_id, vendor_name=name, checks=[decision.to_check_result(raw[c]) for c in order if c in raw],
        missing_items=d.missing_items, flags=d.flags, recommended_decision=d.decision, reasons=d.reasons,
        approvers_required=d.approvers_required, annual_spend_gbp=d.annual_spend_gbp).model_dump()


def _short(args: dict) -> str:
    text = ", ".join(f"{k}={v}" for k, v in args.items())
    return text if len(text) < 90 else text[:87] + "..."


def _report_name(role: str) -> str:
    return {"intake": "VendorRequest", "documents": "DocumentsReport", "compliance": "ComplianceReport",
            "finance": "FinanceReport", "followup": "FollowUpDraft"}[role]


def _describe(role: str, rep: dict | None) -> str:
    if not rep:
        return ""
    if role == "intake":
        return f"vendor='{rep['vendor_name']}' terms={rep['payment_terms_days']} amount={rep['amount_gbp']}/{rep['period']}"
    if role == "documents":
        return f"{rep['check']['result']}, missing={rep['missing_items']}"
    if role == "compliance":
        return f"duplicate={rep['duplicate']['result']} watchlist={rep['watchlist']['result']}"
    if role == "finance":
        return f"bank={rep['bank']['result']} approvers={rep.get('approvers_required')}"
    return f"draft '{rep['subject'][:50]}'"


def case_id_for_request(request_id: str) -> str:
    return case_id_for(request_id)
