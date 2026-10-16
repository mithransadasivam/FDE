"""The policy's decision rules (§7) as plain code, applied to tool results.

Used in three places, never to approve anything:
  * the offline model uses it to behave like a careful agent in demos and tests
  * the reviewer and the trace review use it to check that an agent's recommendation follows from its own evidence
  * the team's evaluation uses it as the reference
A real model's recommendation is NEVER replaced by this: it is compared with it, and differences are reported.
"""
from dataclasses import dataclass, field

from vendor_desk import rules

RESULT_MAP = {
    "documents": {"pass": "pass", "missing": "missing"},
    "duplicate": {"none": "pass", "possible_duplicate": "review", "duplicate": "fail"},
    "watchlist": {"clear": "pass", "near_match": "review", "hit": "fail"},
    "payment_terms": {"pass": "pass", "fail": "fail"},
    "bank": {"pass": "pass", "review": "review", "missing": "missing"},
    "spend": {"pass": "pass"},
}


def to_check_result(tool_output: dict) -> dict:
    """A tool output as the CheckResult dict the Assessment holds."""
    check = tool_output["check"]
    return {
        "check": check,
        "result": RESULT_MAP[check].get(tool_output["result"], "review"),
        "evidence": tool_output["evidence"],
        "tool": tool_output["tool"],
        "policy_section": tool_output["policy_section"],
    }


@dataclass
class Derived:
    decision: str
    flags: list = field(default_factory=list)
    missing_items: list = field(default_factory=list)
    reasons: list = field(default_factory=list)
    approvers_required: int | None = None
    annual_spend_gbp: float | None = None


def derive(results: dict[str, dict], injection: bool) -> Derived:
    """results: tool outputs keyed by check name (documents, duplicate, watchlist, payment_terms, bank, spend)."""
    flags, reasons, missing = [], [], []
    d = results.get("documents")
    if d:
        missing = list(d.get("missing", []))
        if d.get("expired"):
            flags.append("insurance_expired")
        if missing:
            reasons.append(f"Missing or expired: {', '.join(missing)} (§2).")
    dup = results.get("duplicate")
    if dup and dup["result"] == "duplicate":
        flags.append("duplicate_vendor")
        reasons.append(f"Already a vendor: {dup['evidence']} (§3.1).")
    elif dup and dup["result"] == "possible_duplicate":
        flags.append("possible_duplicate")
        reasons.append(f"Possible duplicate: {dup['evidence']} (§3.2).")
    wl = results.get("watchlist")
    if wl and wl["result"] == "hit":
        flags.append("watchlist_hit")
        reasons.append(f"Watch-list hit: {wl['evidence']} (§4.1).")
    elif wl and wl["result"] == "near_match":
        flags.append("watchlist_near_match")
        reasons.append(f"Watch-list near match: {wl['evidence']} (§4.2).")
    bank = results.get("bank")
    for p in (bank or {}).get("problems", []):
        flag = {"§5.2": "bank_country_mismatch", "§5.3": "bank_holder_mismatch", "§5.4": "bank_account_shared"}[
            p["policy_section"]]
        flags.append(flag)
        reasons.append(f"{p['detail'][0].upper()}{p['detail'][1:]} ({p['policy_section']}).")
    terms = results.get("payment_terms")
    if terms and terms["result"] == "fail":
        flags.append("payment_terms_over_limit")
        reasons.append(f"Payment terms of {terms['days']} days are over the limit (§5.1).")
    if injection:
        flags.append("possible_injection")
        reasons.append("The email or a document tries to give the system orders; treated as data and flagged (§1.2).")

    if "duplicate_vendor" in flags or "watchlist_hit" in flags:
        decision = "reject"
    elif {"possible_injection", "possible_duplicate", "watchlist_near_match", "bank_country_mismatch",
          "bank_holder_mismatch", "bank_account_shared"} & set(flags):
        decision = "stop for a person"
    elif missing or "payment_terms_over_limit" in flags:
        decision = "waiting for vendor"
    else:
        decision = "ready for approval"
        reasons.append("Every check passed (§7.4).")
    spend = results.get("spend") or {}
    return Derived(decision, sorted(set(flags)), missing, reasons, spend.get("approvers_required"),
                   spend.get("annual_spend_gbp"))


def required_checks(facts: dict) -> list[str]:
    """Checks that must always run (Phase 3 decision). Terms and spend may be skipped only if the request states none."""
    need = ["documents", "duplicate", "watchlist", "bank"]
    if facts.get("terms_days") is not None:
        need.append("payment_terms")
    if facts.get("amount_gbp") is not None:
        need.append("spend")
    return need


assert set(RESULT_MAP) == set(rules.CHECKS)
