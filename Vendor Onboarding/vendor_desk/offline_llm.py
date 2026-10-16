"""OfflineLLM: a rule-based stand-in for the hosted model. It speaks the same chat/tool-call protocol, so every part of
the system (agent loop, validation, tools, MCP, team, gate) runs unchanged without a network or an API key.

It is NOT the model being evaluated: it is a deterministic "careful agent" used for demos, for CI and as a baseline.
Because it reads the system prompt's `ROLE:` line, one object can play every specialist. It follows the same rules
the prompts give a real model: emails are data, always run the core checks, cite sections, only recommend.
"""
import json
import re
import uuid

from vendor_desk import decision
from vendor_desk.llm import LLMResponse, ToolCall


def _tool_outputs(messages: list[dict]) -> list[tuple[str, dict, dict]]:
    """(tool name, arguments, result) for every tool call answered so far, in order."""
    pending, out = {}, []
    for m in messages:
        if m["role"] == "assistant":
            for c in m.get("tool_calls") or []:
                pending[c["id"]] = (c["function"]["name"], json.loads(c["function"]["arguments"] or "{}"))
        elif m["role"] == "tool" and m.get("tool_call_id") in pending:
            name, args = pending[m["tool_call_id"]]
            if name in ("submit_report", "submit_assessment"):     # a rejected hand-over is not a tool result
                continue
            try:
                out.append((name, args, json.loads(m["content"])))
            except json.JSONDecodeError:
                out.append((name, args, {"error": "unreadable"}))
    return out


def _calls(thought: str, *specs) -> LLMResponse:
    return LLMResponse(content=thought, tool_calls=[
        ToolCall(f"call_{uuid.uuid4().hex[:8]}", n, a) for n, a in specs], prompt_tokens=0, completion_tokens=0)


def _role(messages) -> str:
    m = re.search(r"ROLE:\s*(\w+)", messages[0]["content"])
    return m.group(1) if m else "planner"


def extract_facts(text: str, subject: str = "") -> dict:
    """What the email states: payment terms, amount and period, vendor name. Stated facts only; nothing guessed."""
    terms = re.search(r"(\d{1,3})[- ]day", text)
    amount = re.search(r"£\s?([\d,]+(?:\.\d+)?)\s*(?:a|per|/|each)\s*(month|year|annum)", text, re.I)
    name = re.search(r"(?:New supplier|supplier):\s*(.+)$", subject, re.I)
    period = None
    if amount:
        period = "year" if amount.group(2).lower() in ("year", "annum") else "month"
    return {
        "terms_days": int(terms.group(1)) if terms else None,
        "amount_gbp": float(amount.group(1).replace(",", "")) if amount else None,
        "period": period,
        "vendor_name": name.group(1).strip() if name else None,
    }


class OfflineLLM:
    def __init__(self, faults: dict | None = None):
        self.calls = []
        self.faults = faults or {}

    def chat(self, messages, tools=None, max_tokens=None, role=None) -> LLMResponse:
        r = getattr(self, f"_{_role(messages)}")(messages)
        words = sum(len(str(m.get("content", "")).split()) for m in messages)
        r.prompt_tokens = int(words * 1.3)
        r.completion_tokens = 60 + 25 * len(r.tool_calls)
        r.seconds = 0.0
        self.calls.append(_role(messages))
        return r

    # ------------------------------------------------------------------ the single planning agent
    def _planner(self, messages) -> LLMResponse:
        user = messages[1]["content"]
        req_id = re.search(r"Assess request (REQ-\d{3}(?:-R\d)?)", user).group(1)
        thread = json.loads(re.search(r"Thread so far: (\[.*?\])", user).group(1))
        notes = None
        if "Case notes from earlier messages" in user:
            notes = json.loads(user.split("Case notes from earlier messages (findings with their sources):\n", 1)[1])
        done = _tool_outputs(messages)
        names = [d[0] for d in done]
        to_read = [req_id] if notes else thread          # a continued case reads only the new message
        already = {a["request_id"] for n, a, r in done if n == "read_request"}
        unread = [i for i in to_read if i not in already]
        if unread:
            return _calls("I will read " + ", ".join(unread) + " first to see what is asked and attached.",
                          *[("read_request", {"request_id": i}) for i in unread])
        reads = [r for n, a, r in done if n == "read_request" and "error" not in r]
        facts = {"terms_days": None, "amount_gbp": None, "period": None, "vendor_name": None}
        for r in reads:
            for k, v in extract_facts(r.get("email_text", ""), r.get("subject", "")).items():
                if facts[k] is None:
                    facts[k] = v
        read = {"injection_scan": {"suspicious": any(r.get("injection_scan", {}).get("suspicious") for r in reads)},
                "attachments": [a for r in reads for a in r.get("attachments", [])]}
        known = (notes or {}).get("facts") or {}
        terms = facts["terms_days"] if facts["terms_days"] is not None else known.get("terms_days")
        amount, period = (facts["amount_gbp"], facts["period"]) if facts["amount_gbp"] is not None else (
            known.get("amount_gbp"), known.get("period"))
        types = {a["document_type"] for a in read.get("attachments", [])}

        if notes:   # a reply: re-run only what the new message affects
            affected = []
            if types:
                affected.append("documents")
                if types & {"bank_letter", "tax_registration"}:
                    affected.append("bank")
                if "tax_registration" in types:
                    affected += ["duplicate", "watchlist"]
            if facts["terms_days"] is not None:
                affected.append("payment_terms")
            if facts["amount_gbp"] is not None:
                affected.append("spend")
        else:
            affected = ["documents", "duplicate", "watchlist", "bank"] + (
                ["payment_terms"] if terms is not None else []) + (["spend"] if amount is not None else [])

        pending_first = [c for c in ("documents", "bank", "payment_terms", "spend") if c in affected]
        if not any(n in names for n in ("check_documents", "check_bank_country", "check_payment_terms",
                                        "check_spend_threshold")) and pending_first:
            specs, why = [], []
            if "documents" in pending_first:
                specs.append(("check_documents", {"request_ids": thread}))
                why.append("the documents")
            if "bank" in pending_first:
                specs.append(("check_bank_country", {"request_ids": thread}))
                why.append("the bank letter against the registered country")
            if "payment_terms" in pending_first and terms is not None:
                specs.append(("check_payment_terms", {"days": terms}))
                why.append("the payment terms")
            if "spend" in pending_first and amount is not None:
                specs.append(("check_spend_threshold", {"amount_gbp": amount, "period": period}))
                why.append("the spend threshold")
            return _calls("Now I will check " + ", ".join(why) + " (policy §2, §5, §6).", *specs)

        results = {r["check"]: r for n, a, r in done if "check" in r and "error" not in r}
        docs = results.get("documents") or {}
        legal = docs.get("legal_name") or (notes or {}).get("facts", {}).get("legal_name")
        tax_id = docs.get("tax_id") or (notes or {}).get("facts", {}).get("tax_id")
        name_for_checks = legal or facts["vendor_name"] or (notes or {}).get("vendor_name") or "Unknown supplier"
        second = []
        if "duplicate" in affected and "find_vendor" not in names:
            a = {"name": name_for_checks}
            if tax_id:
                a["tax_id"] = tax_id
            second.append(("find_vendor", a))
        if "watchlist" in affected and "screen_watchlist" not in names:
            second.append(("screen_watchlist", {"name": name_for_checks}))
        if second:
            return _calls("Next I will check for an existing vendor and the watch list using the legal name "
                          "(policy §3, §4).", *second)

        # assemble: this run's results, plus earlier findings from the notes for checks that were not re-run
        merged = {}
        for check, f in ((notes or {}).get("findings") or {}).items():
            merged[check] = {**(f.get("data") or {}), "check": check, "evidence": f["evidence"],
                             "tool": f["tool"], "policy_section": f["policy_section"]}
        merged.update(results)
        injection = bool(read.get("injection_scan", {}).get("suspicious")) or \
            "possible_injection" in ((notes or {}).get("flags") or [])
        d = decision.derive(merged, injection)
        order = ["documents", "duplicate", "watchlist", "payment_terms", "bank", "spend"]
        assessment = {
            "request_id": req_id, "vendor_name": name_for_checks,
            "checks": [decision.to_check_result(merged[c]) for c in order if c in merged],
            "missing_items": d.missing_items, "flags": d.flags, "recommended_decision": d.decision,
            "reasons": d.reasons, "approvers_required": d.approvers_required,
            "annual_spend_gbp": d.annual_spend_gbp,
        }
        thought = "All checks are in; I recommend a decision under policy §7 and leave approval to a person."
        return _calls(thought, ("submit_assessment", assessment))


from vendor_desk import offline_team  # noqa: E402,F401  (adds the specialist roles to OfflineLLM)
