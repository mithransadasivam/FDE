"""Day 17, Activity 3: redact() hides personal data with Presidio, and leaves ordinary answers alone."""

from app.guardrails import check_output
from app.pii import redact


def test_a_mobile_number_and_a_home_address_are_hidden():
    r = redact(
        "Ama is on call: personal mobile +44 7700 900211, home 2 Larch Close, Easthaven."
    )
    assert "900211" not in r["text"] and "Larch Close" not in r["text"]
    assert "<UK_MOBILE>" in r["text"] and "<HOME_ADDRESS>" in r["text"]
    assert r["found"] == ["UK_MOBILE", "HOME_ADDRESS"]


def test_emails_and_card_numbers_are_hidden():
    r = redact("Email b.nguyen@example.com, card 4111 1111 1111 1111.")
    assert r["text"] == "Email <EMAIL_ADDRESS>, card <CREDIT_CARD>."
    assert r["found"] == ["EMAIL_ADDRESS", "CREDIT_CARD"]


def test_an_ordinary_answer_is_unchanged():
    text = "A VPN session can stay connected for a maximum of 12 hours [1]. See ticket INC-1037."
    assert redact(text) == {"text": text, "found": []}


def test_found_holds_types_never_the_data():
    r = redact("Call me on 07700 900348.")
    assert r["found"] and all(t.isupper() and "900348" not in t for t in r["found"])


def test_the_output_guardrail_hides_personal_data():
    out = check_output("Reach her on +44 7700 900211 [2].", judge=None)
    assert out["blocked"] is False
    assert "900211" not in out["text"] and "personal data hidden" in out["reasons"]
