"""What-if lab engine: feed made-up facts through the REAL policy rules and see the decision, with no database, no model and
nothing saved. It builds the same tool-result shapes the real tools return and hands them to decision.derive, so the lab
can never disagree with the system about what the policy means (tests/test_whatif.py checks it against real cases).
"""
from vendor_desk import decision, rules

LADDER = [
    ("§7.1", "REJECT", "a duplicate vendor or a watch-list hit", ("duplicate_vendor", "watchlist_hit")),
    ("§7.2", "STOP FOR A PERSON", "an injection, a possible duplicate, a near match or a bank problem",
     ("possible_injection", "possible_duplicate", "watchlist_near_match", "bank_country_mismatch", "bank_holder_mismatch",
      "bank_account_shared")),
    ("§7.3", "WAITING FOR VENDOR", "a missing or expired document, or terms over the limit",
     ("insurance_expired", "payment_terms_over_limit")),
    ("§7.4", "READY FOR APPROVAL", "every check passed", ()),
]
DOCS = ("tax_registration", "bank_letter", "insurance_certificate")


def simulate(name_similarity: float = 0.2, same_tax_id: bool = False, watchlist_similarity: float = 0.2,
             missing_documents: tuple = (), insurance_expired: bool = False, payment_terms_days: int = 30,
             annual_spend_gbp: float = 12_000, bank_in_registered_country: bool = True, holder_matches: bool = True,
             account_shared: bool = False, injection: bool = False) -> dict:
    """Returns {'decision', 'flags', 'reasons', 'approvers_required', 'rung'} for the facts given."""
    dup = ("duplicate" if same_tax_id or name_similarity >= rules.DUPLICATE_SCORE else
           "possible_duplicate" if name_similarity >= rules.POSSIBLE_DUPLICATE_SCORE else "none")
    wl = ("hit" if watchlist_similarity >= rules.WATCHLIST_HIT_SCORE else
          "near_match" if watchlist_similarity >= rules.WATCHLIST_NEAR_SCORE else "clear")
    missing = list(missing_documents)
    if insurance_expired and "insurance_certificate" not in missing:
        missing.append("insurance_certificate")
    problems = []
    if not bank_in_registered_country:
        problems.append({"policy_section": "§5.2", "detail": "bank country differs from the registered country"})
    if not holder_matches:
        problems.append({"policy_section": "§5.3", "detail": "the account holder does not match the legal name"})
    if account_shared:
        problems.append({"policy_section": "§5.4", "detail": "the account already belongs to a different vendor"})
    results = {
        "documents": {"missing": missing, "expired": ["insurance_certificate"] if insurance_expired else []},
        "duplicate": {"result": dup, "evidence": f"name similarity {name_similarity:.2f}" + (", same tax ID" if same_tax_id else "")},
        "watchlist": {"result": wl, "evidence": f"watch-list similarity {watchlist_similarity:.2f}"},
        "payment_terms": {"result": "pass" if payment_terms_days <= rules.PAYMENT_TERMS_MAX_DAYS else "fail", "days": payment_terms_days},
        "bank": {"result": "review" if problems else "pass", "problems": problems},
        "spend": {"approvers_required": rules.approvers_required(annual_spend_gbp), "annual_spend_gbp": annual_spend_gbp},
    }
    d = decision.derive(results, injection)
    rung = {"reject": 0, "stop for a person": 1, "waiting for vendor": 2, "ready for approval": 3}[d.decision]
    return {"decision": d.decision, "flags": d.flags, "reasons": d.reasons, "approvers_required": d.approvers_required,
            "rung": rung, "missing_items": d.missing_items}
