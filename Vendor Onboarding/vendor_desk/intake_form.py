"""A second channel (stretch goal): a web form that produces exactly the same kind of request file as an email, so the same
case is created whichever way the request arrives. The form never decides anything and its text is data like any email.
"""
import re

from vendor_desk import config, documents

DOC_FILES = {"tax_registration": "tax_registration.txt", "bank_letter": "bank_letter.txt",
             "insurance_certificate": "insurance_certificate.txt"}


def next_request_number() -> int:
    nums = [int(m.group(1)) for p in config.requests_dir().glob("REQ-*.txt")
            if (m := re.match(r"REQ-(\d{3})", p.stem))]
    return max(nums, default=0) + 1


def create_request_from_form(vendor_name: str, requester_email: str, amount_gbp: float | None, period: str,
                             payment_terms_days: int | None, notes: str = "", documents_text: dict | None = None,
                             date: str = "2026-10-16 09:00") -> str:
    """Write data/requests/REQ-NNN.txt (and its attachments) from form fields and return the new request id.
    documents_text: {'tax_registration': text, ...}. Raises ValueError for fields that are not acceptable."""
    vendor_name, requester_email = vendor_name.strip(), requester_email.strip()
    if len(vendor_name) < 2 or len(vendor_name) > 200 or "\n" in vendor_name:
        raise ValueError("Enter the supplier's name on one line (2 to 200 characters).")
    if not re.match(r"^[^@\s]+@[^@\s]+\.[a-z]+$", requester_email):
        raise ValueError("Enter a valid requester email address.")
    if period not in ("month", "year"):
        raise ValueError("The amount must be per month or per year.")
    if amount_gbp is not None and not 0 <= amount_gbp <= 100_000_000:
        raise ValueError("The amount must be between 0 and 100,000,000.")
    if payment_terms_days is not None and not 0 <= payment_terms_days <= 365:
        raise ValueError("Payment terms must be between 0 and 365 days.")
    n = next_request_number()
    request_id = f"REQ-{n:03d}"
    att_dir = config.requests_dir() / "attachments" / request_id
    names = []
    for dtype, text in (documents_text or {}).items():
        if dtype not in DOC_FILES or not text.strip():
            continue
        if documents.parse_document(text)["type"] != dtype:
            raise ValueError(f"The {dtype.replace('_', ' ')} file does not look like that document type.")
        att_dir.mkdir(parents=True, exist_ok=True)
        (att_dir / DOC_FILES[dtype]).write_text(text, encoding="utf-8")
        names.append(f"{request_id}/{DOC_FILES[dtype]}")
    parts = [f"New supplier request from the web form: {vendor_name}."]
    if amount_gbp is not None:
        parts.append(f"Expected spend is about £{amount_gbp:,.0f} a {period}.")
    if payment_terms_days is not None:
        parts.append(f"They have asked for {payment_terms_days}-day payment terms.")
    if names:
        parts.append("Documents are attached.")
    if notes.strip():
        parts.append(notes.strip())
    headers = [f"Message-ID: <{request_id.lower()}@example.com>", f"From: {requester_email}",
               "To: procurement@marlowefinch.example.com", f"Date: {date}", f"Subject: New supplier: {vendor_name}",
               "Kind: request", "Channel: web form", "Attachments: " + ("; ".join(names) if names else "none")]
    (config.requests_dir() / f"{request_id}.txt").write_text("\n".join(headers) + "\n\n" + " ".join(parts) + "\n",
                                                             encoding="utf-8")
    return request_id


def unprocessed_requests(existing_case_ids: set[str]) -> list[str]:
    """Request ids (not replies) that have no case yet."""
    out = []
    for rid in documents.list_request_ids():
        if "-R" in rid:
            continue
        if "VOB-" + rid[4:7] not in existing_case_ids:
            out.append(rid)
    return out


def waiting_replies(cases: list[dict]) -> dict[str, str]:
    """{case_id: reply request id} for cases waiting for a vendor whose reply file exists and has not been used."""
    out = {}
    for c in cases:
        if c["status"] != "WAITING_FOR_VENDOR":
            continue
        for rid in documents.list_request_ids():
            if rid.startswith("REQ-" + c["case_id"][4:7] + "-R") and rid not in c["request_ids"]:
                out[c["case_id"]] = rid
                break
    return out

