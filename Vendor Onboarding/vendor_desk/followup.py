"""Follow-up emails to the vendor (policy §8). Always a DRAFT: nothing here sends anything.

draft_followup() is the deterministic template (the fallback and what Part 1 uses). The team's follow-up writer is a
model that writes the same email in its own words; check_draft() verifies that either one lists every item, never
contains bank details and never claims to have been sent.
"""
import re

from vendor_desk.contracts import FollowUpDraft
from vendor_desk.safety import redact

WHY = {
    "tax_registration": ("a tax registration certificate showing your legal name, tax ID and registered address",
                         "so we can confirm the legal entity we will be paying (our onboarding policy §2.1)"),
    "bank_letter": ("a bank details letter on your bank's letterhead, in the same name as your registration",
                    "so payments reach the right account (policy §2.2)"),
    "insurance_certificate": ("a current public liability insurance certificate",
                              "because we can only start work with a supplier whose cover is in date (policy §2.3)"),
}


def requested_items(assessment: dict) -> list[str]:
    items = []
    expiry = {c["check"]: c["evidence"] for c in assessment["checks"]}.get("documents", "")
    for doc in assessment["missing_items"]:
        what, why = WHY[doc]
        if doc == "insurance_certificate" and "expired" in expiry:
            what = "a renewed public liability insurance certificate (the one we hold has expired)"
        items.append(f"{what}, {why}")
    if "payment_terms_over_limit" in assessment["flags"]:
        items.append("confirmation that you can accept payment terms of 45 days or fewer, because our policy "
                     "(§5.1) does not allow longer terms")
    return items


def draft_followup(assessment: dict, requester_email: str, request_id: str) -> dict | None:
    items = requested_items(assessment)
    if assessment["recommended_decision"] != "waiting for vendor" or not items:
        return None
    vendor = assessment["vendor_name"]
    lines = "\n".join(f"  {i}. {item[0].upper() + item[1:]}" for i, item in enumerate(items, 1))
    body = (f"Hello,\n\nThank you for your interest in supplying Marlowe & Finch Ltd. We are setting {vendor} up as a "
            f"supplier and, before we can finish, we need the following:\n\n{lines}\n\n"
            "Once we have these we will carry on straight away; there is no need to resend anything you have "
            "already given us. If anything is unclear, just reply to this message.\n\n"
            "Kind regards,\nProcurement team, Marlowe & Finch Ltd\n\n"
            "(DRAFT for a person to review. Not sent.)")
    return FollowUpDraft(request_id=request_id, to=f"{vendor} contact (request raised by {requester_email})",
                         subject=f"Marlowe & Finch onboarding: information needed for {vendor}",
                         body=body, requested_items=items).model_dump()


def check_draft(draft: dict, assessment: dict) -> list[str]:
    """Problems with a draft (empty list = fine): every item mentioned, no bank details, not claimed as sent."""
    problems = []
    body = draft["body"].lower()
    needs = {"tax_registration": "tax registration", "bank_letter": "bank", "insurance_certificate": "insurance"}
    for doc in assessment["missing_items"]:
        if needs[doc] not in body:
            problems.append(f"the draft does not ask for the {doc.replace('_', ' ')}")
    if "payment_terms_over_limit" in assessment["flags"] and "45" not in body:
        problems.append("the draft does not mention the 45-day payment terms limit")
    if redact(draft["body"]) != draft["body"]:
        problems.append("the draft contains something that looks like bank details")
    if re.search(r"\b(has been sent|i have sent|we have sent)\b", body):
        problems.append("the draft claims to have been sent")
    return problems


def custom_followup(vendor_name: str, requester_email: str, request_id: str, note: str) -> dict:
    """A draft for 'ask the vendor' when a person wants something that is not a missing document."""
    note = redact(note.strip())
    body = (f"Hello,\n\nThank you for your interest in supplying Marlowe & Finch Ltd. While setting {vendor_name} up as a "
            f"supplier we need one more thing from you:\n\n  1. {note}\n\nOnce we have it we will carry on straight "
            "away. If anything is unclear, just reply to this message.\n\nKind regards,\n"
            "Procurement team, Marlowe & Finch Ltd\n\n(DRAFT for a person to review. Not sent.)")
    return FollowUpDraft(request_id=request_id, to=f"{vendor_name} contact (request raised by {requester_email})",
                         subject=f"Marlowe & Finch onboarding: a question about {vendor_name}",
                         body=body, requested_items=[note]).model_dump()
