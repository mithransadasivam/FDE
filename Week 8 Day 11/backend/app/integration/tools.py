"""What the MCP server can do, as plain functions of the person asking (done, not a ticket).

Each tool checks the scope it needs, gets a token for the bank's system with downstream_token() (ENG-802) and calls it.
The bank's systems apply their own rules for the person; a refusal comes back as ToolRefused with the system's reason.
"""

import httpx

from app.config import BANK_URL
from app.integration.downstream import downstream_token
from app.integration.models import Identity, ToolRefused

_http: httpx.Client | None = None


def bank_http() -> httpx.Client:
    """The HTTP client for the bank's systems. Tests swap it for one that talks to the bank in-process."""
    global _http
    if _http is None:
        _http = httpx.Client(timeout=20)
    return _http


def set_bank_http(client: httpx.Client | None) -> None:
    global _http
    _http = client


def _call(identity: Identity, scope: str, audience: str, method: str, path: str, **kw) -> dict:
    if scope not in identity.scopes:
        raise ToolRefused(f"Your sign-in does not allow this: it has no {scope} scope")
    http = bank_http()
    token = downstream_token(identity, audience, http)
    r = http.request(method, f"{BANK_URL}{path}", headers={"Authorization": f"Bearer {token}"}, **kw)
    if r.status_code >= 400:
        try:
            why = r.json().get("detail", r.text)
        except ValueError:
            why = r.text
        raise ToolRefused(str(why))
    return r.json()


def find_customer(identity: Identity, query: str = "") -> dict:
    """Search the CRM by name or customer id. An empty query lists every customer this person may see."""
    return _call(identity, "kyc.read", "crm", "GET", "/crm/customers", params={"q": query})


def get_customer(identity: Identity, customer_id: str) -> dict:
    """One customer from the CRM: details, contact history and notes."""
    return _call(identity, "kyc.read", "crm", "GET", f"/crm/customers/{customer_id}")


def add_customer_note(identity: Identity, customer_id: str, text: str) -> dict:
    """Add a note to a customer in the CRM, in the person's name."""
    return _call(identity, "kyc.write", "crm", "POST", f"/crm/customers/{customer_id}/notes", json={"text": text})


def list_exceptions(identity: Identity, status: str = "") -> dict:
    """KYC exceptions this person may see: open, in_progress or resolved; empty for all."""
    return _call(identity, "kyc.read", "kyc-exceptions", "GET", "/kyc/tickets", params={"status": status})


def get_exception(identity: Identity, ticket_id: str) -> dict:
    """One KYC exception with its comments."""
    return _call(identity, "kyc.read", "kyc-exceptions", "GET", f"/kyc/tickets/{ticket_id}")


def comment_on_exception(identity: Identity, ticket_id: str, text: str) -> dict:
    """Add a comment to a KYC exception, in the person's name."""
    return _call(identity, "kyc.write", "kyc-exceptions", "POST", f"/kyc/tickets/{ticket_id}/comments", json={"text": text})


def assign_exception(identity: Identity, ticket_id: str, analyst_id: str) -> dict:
    """Assign a KYC exception to an analyst in its team. The ticketing system allows team leads only."""
    return _call(identity, "kyc.write", "kyc-exceptions", "POST", f"/kyc/tickets/{ticket_id}/assign", json={"analyst_id": analyst_id})


def list_documents(identity: Identity, customer_id: str) -> dict:
    """The documents on one customer's file, as metadata (no content)."""
    return _call(identity, "kyc.read", "documents", "GET", f"/docs/customers/{customer_id}/documents")


def get_document(identity: Identity, doc_id: str) -> dict:
    """One document. The store allows 20 an hour per person."""
    return _call(identity, "kyc.read", "documents", "GET", f"/docs/documents/{doc_id}")


TOOLS = {f.__name__: f for f in [find_customer, get_customer, add_customer_note, list_exceptions, get_exception,
                                 comment_on_exception, assign_exception, list_documents, get_document]}
