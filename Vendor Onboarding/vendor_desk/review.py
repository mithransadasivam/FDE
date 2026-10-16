"""Trace review (Phase 4): reads a finished run and flags what went wrong, in plain words.

Flags: step_limit_reached, repeated_call, tool_error, decision_without_evidence, rule_without_section, plus extras that
protect the rules of this project: required_check_missing, decision_inconsistent (the recommendation does not follow from
the agent's own evidence under policy §7), injection_not_flagged, private_data_in_trace.
"""
import json
import re

from vendor_desk import decision

ACCOUNT_LIKE = re.compile(r"\b\d{8,12}\b|\b\d{2}-\d{2}-\d{2}\b")
RULE_WORDS = re.compile(r"\b(policy|rule|limit|threshold|allowed|not allowed|over|above|below)\b", re.I)


def problem(code: str, detail: str, severity: str = "error") -> dict:
    return {"code": code, "severity": severity, "detail": detail}


def review_run(run, notes_before: dict | None = None) -> list[dict]:
    """Problems found in one AgentRun (empty list = clean). notes_before: the case notes the run started from."""
    out = []
    if run.status == "step_limit":
        out.append(problem("step_limit_reached", run.message))
    for kind, code in (("repeated_call", "repeated_call"), ("tool_error", "tool_error")):
        for e in run.trace:
            if e["type"] == kind:
                out.append(problem(code, f"step {e['step']}: {e.get('name')} {e.get('error', '')}".strip(), "warn"))
    if run.status not in ("ok", "step_limit"):
        out.append(problem(run.status, run.message))
    a = run.assessment
    if a:
        out += _review_assessment(a, run, notes_before)
    if ACCOUNT_LIKE.search(json.dumps(run.trace)):
        out.append(problem("private_data_in_trace", "something that looks like an account number is in the trace"))
    return out


def _review_assessment(a: dict, run, notes_before) -> list[dict]:
    out = []
    ran = {tr["result"].get("check"): tr["result"] for tr in run.tool_results if "error" not in tr["result"]}
    from_notes = (notes_before or {}).get("findings", {})
    available = {**{k: {**(v.get("data") or {}), "check": k, "evidence": v["evidence"], "tool": v["tool"],
                        "policy_section": v["policy_section"]} for k, v in from_notes.items()}, **ran}
    for c in a["checks"]:
        raw = available.get(c["check"])
        if not raw:
            out.append(problem("decision_without_evidence",
                               f"the {c['check']} check was reported but no tool result supports it"))
        elif c["tool"] != raw.get("tool"):
            out.append(problem("decision_without_evidence",
                               f"the {c['check']} check cites {c['tool']} but the evidence came from {raw.get('tool')}"))
        elif decision.to_check_result(raw)["result"] != c["result"]:
            out.append(problem("decision_without_evidence",
                               f"the {c['check']} check says '{c['result']}' but {c['tool']} returned "
                               f"'{decision.to_check_result(raw)['result']}'"))
        elif c["policy_section"] != raw.get("policy_section"):
            out.append(problem("rule_without_section",
                               f"the {c['check']} check cites {c['policy_section']} but the tool applied "
                               f"{raw.get('policy_section')}", "warn"))
    reported = {c["check"] for c in a["checks"]}
    for need in ("documents", "duplicate", "watchlist", "bank"):
        if need not in reported:
            out.append(problem("required_check_missing", f"the {need} check always runs but is not in the assessment"))
    if a["recommended_decision"] == "ready for approval" and (len(reported) < 4 or any(
            c["result"] != "pass" for c in a["checks"])):
        out.append(problem("decision_without_evidence", "ready for approval without every check passing"))
    for r in a["reasons"]:
        if RULE_WORDS.search(r) and not re.search(r"§\d", r):
            out.append(problem("rule_without_section", f"reason applies a rule without a section number: '{r[:80]}'"))
    # does the recommendation follow from the evidence the agent itself collected?
    results = {k: v for k, v in available.items() if k in decision.RESULT_MAP}
    injection = _injection_seen(run, notes_before)
    d = decision.derive(results, injection)
    if d.decision != a["recommended_decision"]:
        out.append(problem("decision_inconsistent",
                           f"evidence supports '{d.decision}' under §7 but the agent recommended "
                           f"'{a['recommended_decision']}'"))
    if injection and "possible_injection" not in a["flags"]:
        out.append(problem("injection_not_flagged", "the request tried to give orders but possible_injection is missing"))
    return out


def _injection_seen(run, notes_before) -> bool:
    for tr in run.tool_results:
        if tr["name"] == "read_request" and tr["result"].get("injection_scan", {}).get("suspicious"):
            return True
    return "possible_injection" in ((notes_before or {}).get("flags") or [])
