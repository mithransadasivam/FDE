"""The offline stand-in for the team's specialists (see offline_llm.py). Each role reads its `Task: {...}` message, calls
its tools, and hands over a report that fits its contract, exactly as a careful model would.

Test/demo hook: OfflineLLM(faults={"compliance": "wrong"}) makes a role misbehave on its FIRST attempt so the reviewer's
send-back and the handoff retry can be shown on purpose:
  wrong          mislabel a result (the reviewer must catch it and send the work back)
  invalid        hand over an object that does not fit the contract (one retry, then it is fixed)
  always_invalid never fits (the case must stop)
"""
import json

from vendor_desk import decision
from vendor_desk.followup import custom_followup, draft_followup
from vendor_desk.llm import LLMResponse
from vendor_desk.offline_llm import OfflineLLM, _calls, _tool_outputs, extract_facts


def _payload(messages) -> dict:
    text = messages[1]["content"]
    return json.loads(text.split("Task: ", 1)[1].split("\nYour previous report", 1)[0])


def _was_sent_back(messages) -> bool:
    return "previous report was sent back" in messages[1]["content"]


def _bad_attempts(messages) -> int:
    return sum(1 for m in messages if m["role"] == "tool" and "does not fit the required shape" in m["content"])


def _submit(thought, report):
    return _calls(thought, ("submit_report", report))


def _fault(self, role, messages):
    mode = self.faults.get(role)
    if mode == "always_invalid":
        return "invalid"
    if mode == "invalid" and _bad_attempts(messages) == 0:
        return "invalid"
    if mode == "always_wrong":
        return "wrong"
    if mode == "wrong" and not _was_sent_back(messages):
        return "wrong"
    return None


def _retry_failed(done):
    """If a tool call failed, a careful specialist tries the same call again (the loop bounds how often)."""
    failed = [(n, a) for n, a, r in done if "error" in r]
    return _calls("A tool failed; I will try it again.", *failed) if failed else None


def _intake(self, messages):
    p = _payload(messages)
    done = _tool_outputs(messages)
    if not done:
        return _calls("I will read the request email(s) to record what is stated.",
                      *[("read_request", {"request_id": i}) for i in p["request_ids"]])
    if (again := _retry_failed(done)):
        return again
    reads = [r for n, a, r in done if n == "read_request" and "error" not in r]
    facts = {"terms_days": None, "amount_gbp": None, "period": None, "vendor_name": None}
    for r in reads:
        for k, v in extract_facts(r.get("email_text", ""), r.get("subject", "")).items():
            if facts[k] is None:
                facts[k] = v
    return _submit("I have the facts; handing over the vendor request.", {
        "request_id": p["request_ids"][-1], "requester_email": reads[0]["from"] if reads else "unknown@example.com",
        "vendor_name": facts["vendor_name"] or "Unknown supplier", "goods_or_services": "",
        "payment_terms_days": facts["terms_days"], "amount_gbp": facts["amount_gbp"], "period": facts["period"],
        "attachment_types": sorted({a["document_type"] for r in reads for a in r.get("attachments", [])}),
        "asks_to_skip_or_approve": any(r.get("injection_scan", {}).get("suspicious") for r in reads)})


def _documents(self, messages):
    p = _payload(messages)
    done = _tool_outputs(messages)
    if not done:
        return _calls("I will check the three required documents across the whole thread (policy §2).",
                      ("check_documents", {"request_ids": p["thread"]}))
    if (again := _retry_failed(done)):
        return again
    r = done[0][2]
    if self._fault("documents", messages) == "invalid":
        return _submit("Handing over my report.", {"request_id": p["thread"][-1]})
    return _submit("Documents checked; handing over the report.", {
        "request_id": p["thread"][-1], "check": decision.to_check_result(r), "missing_items": r["missing"],
        "legal_name": r.get("legal_name"), "tax_id": r.get("tax_id"), "registered_country": r.get("registered_country")})


def _compliance(self, messages):
    p = _payload(messages)
    done = _tool_outputs(messages)
    if not done:
        a = {"name": p["vendor_name"]}
        if p.get("tax_id"):
            a["tax_id"] = p["tax_id"]
        return _calls("I will check duplicates and the watch list with the legal name (policy §3, §4).",
                      ("find_vendor", a), ("screen_watchlist", {"name": p["vendor_name"]}))
    if (again := _retry_failed(done)):
        return again
    dup = next(r for n, a, r in done if n == "find_vendor")
    wl = next(r for n, a, r in done if n == "screen_watchlist")
    dup_c, wl_c = decision.to_check_result(dup), decision.to_check_result(wl)
    if self._fault("compliance", messages) == "wrong" and wl_c["result"] != "pass":
        wl_c["result"] = "pass"          # a careless transcription: the reviewer must catch this
    flags = {"duplicate": ["duplicate_vendor"], "possible_duplicate": ["possible_duplicate"]}.get(dup["result"], [])
    flags += {"hit": ["watchlist_hit"], "near_match": ["watchlist_near_match"]}.get(wl["result"], [])
    return _submit("Compliance checks done; handing over the report.",
                   {"request_id": p["request_id"], "duplicate": dup_c, "watchlist": wl_c, "flags": flags})


def _finance(self, messages):
    p = _payload(messages)
    done = _tool_outputs(messages)
    if not done:
        specs = []
        if p.get("terms_days") is not None:
            specs.append(("check_payment_terms", {"days": p["terms_days"]}))
        specs.append(("check_bank_country", {"request_ids": p["thread"]}))
        if p.get("amount_gbp") is not None:
            specs.append(("check_spend_threshold", {"amount_gbp": p["amount_gbp"], "period": p["period"]}))
        return _calls("I will check the payment terms, the bank letter and the spend threshold (policy §5, §6).", *specs)
    if (again := _retry_failed(done)):
        return again
    by = {r["check"]: r for n, a, r in done if "check" in r and "error" not in r}
    if self._fault("finance", messages) == "invalid":
        return _submit("Handing over my report.", {"request_id": p["thread"][-1], "bank": "fine"})
    sections = {"§5.2": "bank_country_mismatch", "§5.3": "bank_holder_mismatch", "§5.4": "bank_account_shared"}
    flags = [sections[x["policy_section"]] for x in by.get("bank", {}).get("problems", [])]
    if by.get("payment_terms", {}).get("result") == "fail":
        flags.append("payment_terms_over_limit")
    report = {"request_id": p["thread"][-1], "bank": decision.to_check_result(by["bank"]), "flags": flags}
    if "payment_terms" in by:
        report["payment_terms"] = decision.to_check_result(by["payment_terms"])
    if "spend" in by:
        report["spend"] = decision.to_check_result(by["spend"])
        report["approvers_required"] = by["spend"]["approvers_required"]
        report["annual_spend_gbp"] = by["spend"]["annual_spend_gbp"]
    return _submit("Finance checks done; handing over the report.", report)


def _followup(self, messages):
    p = _payload(messages)
    d = draft_followup(p["assessment"], p["requester"], p["request_id"])
    if d is None and p.get("note"):
        d = custom_followup(p["assessment"]["vendor_name"], p["requester"], p["request_id"], p["note"])
    if self._fault("followup", messages) == "invalid":
        return _submit("Here is the draft.", {"request_id": p["request_id"], "to": "x"})
    return _submit("Here is a polite draft that lists exactly what is needed.", d)


def _supervisor(self, messages):
    """A model supervisor stand-in: picks the first legal option (or an illegal one when faults={'supervisor': 'wrong'})."""
    options = json.loads(messages[1]["content"].split("Task: ", 1)[1])["options"]
    return LLMResponse(content="nonsense" if self.faults.get("supervisor") == "wrong" else options[0])


OfflineLLM._supervisor = _supervisor
OfflineLLM._intake, OfflineLLM._documents, OfflineLLM._compliance = _intake, _documents, _compliance
OfflineLLM._finance, OfflineLLM._followup, OfflineLLM._fault = _finance, _followup, _fault
