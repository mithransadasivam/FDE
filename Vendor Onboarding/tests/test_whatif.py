"""The what-if lab uses the real rules: its answers must match the real cases."""
from vendor_desk.whatif import simulate


def test_matches_the_hard_cases():
    assert simulate(same_tax_id=True, name_similarity=0.70)["decision"] == "reject"                    # REQ-003
    assert simulate(watchlist_similarity=1.0)["decision"] == "reject"                                   # REQ-005
    assert simulate(watchlist_similarity=0.864)["decision"] == "stop for a person"                      # REQ-004
    assert simulate(name_similarity=0.756)["decision"] == "stop for a person"                           # REQ-013
    assert simulate(bank_in_registered_country=False)["flags"] == ["bank_country_mismatch"]             # REQ-006
    assert simulate(account_shared=True)["decision"] == "stop for a person"                             # REQ-015
    assert simulate(holder_matches=False)["decision"] == "stop for a person"                            # REQ-018
    assert simulate(insurance_expired=True)["decision"] == "waiting for vendor"                         # REQ-007
    assert simulate(missing_documents=("tax_registration", "bank_letter"))["missing_items"] == ["tax_registration", "bank_letter"]
    assert simulate(payment_terms_days=60)["decision"] == "waiting for vendor"                          # REQ-010
    assert simulate(injection=True)["decision"] == "stop for a person"                                  # REQ-011


def test_the_spend_threshold_and_a_clean_case():
    assert simulate(annual_spend_gbp=24_500)["approvers_required"] == 1
    assert simulate(annual_spend_gbp=25_000)["approvers_required"] == 1
    assert simulate(annual_spend_gbp=25_200)["approvers_required"] == 2
    clean = simulate()
    assert clean["decision"] == "ready for approval" and clean["flags"] == [] and clean["rung"] == 3


def test_the_precedence_order_holds():
    # reject beats stop beats waiting, whatever else is wrong
    everything = simulate(same_tax_id=True, injection=True, insurance_expired=True, payment_terms_days=90, account_shared=True)
    assert everything["decision"] == "reject" and everything["rung"] == 0
    assert simulate(injection=True, insurance_expired=True)["decision"] == "stop for a person"
