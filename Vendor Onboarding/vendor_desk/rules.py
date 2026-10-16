"""The numbers from docs/ONBOARDING_POLICY.md as code. tests/test_policy.py checks they still match
the document, so the policy and the code cannot drift apart without a failing test."""

PAYMENT_TERMS_MAX_DAYS = 45            # §5.1
DUPLICATE_SCORE = 0.95                 # §3.1
POSSIBLE_DUPLICATE_SCORE = 0.75        # §3.2
WATCHLIST_HIT_SCORE = 0.97             # §4.1
WATCHLIST_NEAR_SCORE = 0.80            # §4.2
SPEND_THRESHOLD_GBP = 25_000           # §6.1, §6.2
STALE_MANAGER_DAYS = 2                 # §9.1
STALE_EXPIRE_DAYS = 7                  # §9.2

DECISIONS = ("ready for approval", "waiting for vendor", "reject", "stop for a person")
REQUIRED_DOCUMENTS = ("tax_registration", "bank_letter", "insurance_certificate")
FLAGS = (
    "possible_injection", "duplicate_vendor", "possible_duplicate", "watchlist_hit", "watchlist_near_match",
    "bank_country_mismatch", "bank_holder_mismatch", "bank_account_shared", "insurance_expired",
    "payment_terms_over_limit",
)
CHECKS = ("documents", "duplicate", "watchlist", "payment_terms", "bank", "spend")


def approvers_required(annual_spend_gbp: float | None) -> int:
    """§6.1 / §6.2."""
    if annual_spend_gbp is None:
        return 1
    return 2 if annual_spend_gbp > SPEND_THRESHOLD_GBP else 1
