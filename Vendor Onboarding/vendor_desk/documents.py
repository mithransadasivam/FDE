"""Reading request emails and their attached documents, and the policy text. Read-only.

Nothing here returns a bank account number: parse_document() keeps the private fields under a separate key that only
the checks in tools.py (and the one approved write) ever touch, and tool results are redacted again before they leave.
"""
import re
from datetime import date

from vendor_desk import config

REQUEST_ID = re.compile(r"^REQ-\d{3}(-R\d)?$")

DOC_TYPES = {
    "tax registration certificate": "tax_registration",
    "bank details letter": "bank_letter",
    "insurance certificate": "insurance_certificate",
}
PRIVATE_FIELDS = ("account_number", "sort_code")


class ToolProblem(Exception):
    """A problem the model should read (unknown id, missing file, ...). Never a crash."""


def list_request_ids() -> list[str]:
    return sorted(p.stem for p in config.requests_dir().glob("REQ-*.txt"))


def load_request(request_id: str) -> dict:
    if not isinstance(request_id, str) or not REQUEST_ID.match(request_id):
        raise ToolProblem(f"'{request_id}' is not a valid request id. Use the form REQ-001 (or REQ-001-R1 for a reply).")
    path = config.requests_dir() / f"{request_id}.txt"
    if not path.exists():
        known = ", ".join(list_request_ids()[:5])
        raise ToolProblem(f"There is no request file for {request_id}. Known requests start: {known} ...")
    head, _, body = path.read_text(encoding="utf-8").partition("\n\n")
    headers = {}
    for line in head.splitlines():
        k, _, v = line.partition(":")
        headers[k.strip().lower()] = v.strip()
    names = [n.strip() for n in headers.get("attachments", "").split(";") if n.strip() and n.strip() != "none"]
    return {
        "request_id": request_id, "from": headers.get("from", ""), "to": headers.get("to", ""),
        "date": headers.get("date", ""), "subject": headers.get("subject", ""), "kind": headers.get("kind", "request"),
        "case": headers.get("case", ""), "attachments": names, "body": body.strip(),
    }


def parse_document(text: str) -> dict:
    """{'type': ..., 'fields': {key: value}} from a short 'Key: value' text document."""
    fields, doc_type = {}, None
    for line in text.splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        key = re.sub(r"[^a-z0-9]+", "_", k.strip().lower()).strip("_")
        if key == "document":
            doc_type = DOC_TYPES.get(v.strip().lower())
        elif key:
            fields[key] = v.strip()
    return {"type": doc_type, "fields": fields}


def read_attachment(name: str) -> str:
    path = (config.requests_dir() / "attachments" / name).resolve()
    base = (config.requests_dir() / "attachments").resolve()
    if base not in path.parents or not path.exists():
        raise ToolProblem(f"The attachment {name} could not be found.")
    return path.read_text(encoding="utf-8")


def documents_for(request_ids: list[str]) -> tuple[dict, list[dict]]:
    """All documents attached across a thread of messages (original request plus replies).
    Later messages replace earlier documents of the same type. Returns ({type: parsed}, [messages])."""
    docs, messages = {}, []
    for rid in request_ids:
        msg = load_request(rid)
        messages.append(msg)
        for name in msg["attachments"]:
            parsed = parse_document(read_attachment(name))
            parsed["file"] = name
            if parsed["type"]:
                docs[parsed["type"]] = parsed
    return docs, messages


def insurance_status(fields: dict, as_of: date) -> tuple[bool, str]:
    """(valid, reason) for an insurance certificate on the assessment date (§2.3)."""
    raw = fields.get("expiry_date", "")
    try:
        expiry = date.fromisoformat(raw)
    except ValueError:
        return False, f"expiry date '{raw}' could not be read"
    if expiry < as_of:
        return False, f"expired on {expiry.isoformat()}"
    return True, f"valid until {expiry.isoformat()}"


# ---------------------------------------------------------------- the policy text
def policy_sections() -> dict[str, str]:
    """{'§3.2': text, ...} plus whole sections {'§3': heading and all bullets}."""
    sections, top = {}, {}
    current = None
    for line in config.policy_path().read_text(encoding="utf-8").splitlines():
        h = re.match(r"^##\s+(§\d{1,2})\s+(.*)$", line)
        if h:
            current = h.group(1)
            top[current] = [f"{h.group(1)} {h.group(2)}"]
            continue
        b = re.match(r"^-\s+\*\*(§\d{1,2}\.\d{1,2})([^*]*)\*\*\s*(.*)$", line)
        if b:
            text = f"{b.group(2).strip()} {b.group(3).strip()}".strip()
            sections[b.group(1)] = text
            if current:
                top[current].append(f"{b.group(1)} {text}")
        elif current and line.strip().startswith("-") and top.get(current):
            top[current].append(line.strip()[1:].strip())
    for k, v in top.items():
        sections[k] = "\n".join(v)
    return sections


def lookup_policy(section: str) -> dict:
    key = section.strip()
    if not key.startswith("§"):
        key = "§" + key
    sections = policy_sections()
    if key not in sections:
        raise ToolProblem(f"There is no policy section {key}. Sections: " + ", ".join(sorted(
            (k for k in sections if "." not in k), key=lambda s: int(s[1:]))) + " (or a rule such as §3.2).")
    return {"section": key, "text": sections[key]}
