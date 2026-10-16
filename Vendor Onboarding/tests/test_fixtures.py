"""Phase 0 checkpoint: the cases, the files they name, and the policy numbers the code relies on."""
import csv
import re

from vendor_desk import config, rules, safety

ROOT = config.ROOT


def cases():
    with open(ROOT / "data" / "onboarding_cases.csv", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_at_least_12_cases_and_every_file_exists():
    rows = cases()
    assert len(rows) >= 12
    for r in rows:
        assert (ROOT / "data" / "requests" / r["request_file"]).exists(), r["id"]
        assert r["expected_decision"] in rules.DECISIONS


def test_every_attachment_named_in_an_email_exists():
    for p in (ROOT / "data" / "requests").glob("REQ-*.txt"):
        line = next(l for l in p.read_text(encoding="utf-8").splitlines() if l.startswith("Attachments:"))
        for name in [n.strip() for n in line.split(":", 1)[1].split(";") if n.strip() and n.strip() != "none"]:
            assert (ROOT / "data" / "requests" / "attachments" / name).exists(), name


def test_hard_cases_are_present():
    hard = " ".join(r["hard_case"] for r in cases())
    for needle in ("duplicate", "watch-list", "different country", "expired", "below", "above", "skip the checks"):
        assert needle in hard, needle
    assert sum(1 for r in cases() if r["hard_case"]) >= 3


def test_nothing_is_real_only_example_com_addresses():
    emails = set()
    for p in (ROOT / "data").rglob("*.txt"):
        emails |= set(re.findall(r"[\w.+-]+@[\w.-]+", p.read_text(encoding="utf-8")))
    assert emails and all(e.endswith("example.com") for e in emails), emails


def test_policy_numbers_in_code_match_the_policy_document():
    text = config.policy_path().read_text(encoding="utf-8")
    assert f"**{rules.PAYMENT_TERMS_MAX_DAYS} days or fewer**" in text
    assert f"**{rules.DUPLICATE_SCORE}" in text and f"**{rules.POSSIBLE_DUPLICATE_SCORE}" in text
    assert f"**{rules.WATCHLIST_HIT_SCORE}" in text and f"**{rules.WATCHLIST_NEAR_SCORE}" in text
    assert f"£{rules.SPEND_THRESHOLD_GBP:,}" in text
    assert "**2 days**" in text and "**7 days**" in text


def test_injection_scanner_flags_the_attacks_and_not_the_normal_emails():
    flagged = {}
    for p in (ROOT / "data" / "requests").glob("REQ-*.txt"):
        body = p.read_text(encoding="utf-8")
        for att in (ROOT / "data" / "requests" / "attachments" / p.stem).glob("*.txt"):
            body += "\n" + att.read_text(encoding="utf-8")
        flagged[p.stem] = safety.scan_injection(body)
    assert {k for k, v in flagged.items() if v} == {"REQ-011", "REQ-016", "REQ-017"}, flagged


def test_redact_removes_account_numbers_and_sort_codes():
    out = safety.redact("Account number: 99310442\nSort code: 99-10-01\nAlso 99310442 and 99-10-01 inline.")
    assert "99310442" not in out and "99-10-01" not in out
