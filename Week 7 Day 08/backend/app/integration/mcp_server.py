"""The FDE's remote MCP server over the bank's CRM and KYC exceptions (done, not a ticket).

Run it:            cd backend && python -m app.integration.mcp_server            (http://localhost:8200/mcp)
Connect Claude Code:  claude mcp add --transport http kestrelmoor-kyc http://localhost:8200/mcp   then /mcp to sign in

Every request needs a bearer token from the bank's sign-in service. Without one the server answers 401 and points to
/.well-known/oauth-protected-resource (RFC 9728), which names the bank as the authorization server: that is how Claude Code
finds where to sign the person in. Each token is checked by verify_access_token() (ENG-801); each tool then calls the
bank as that person (ENG-802).
"""

import os
import time

import httpx
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError

from app import store
from app.config import BANK_ISSUER, BANK_URL, MCP_RESOURCE, MCP_URL
from app.integration import tools
from app.integration.models import Identity, TokenRejected, ToolRefused
from app.integration.tokens import verify_access_token

REQUIRED_SCOPES = ["kyc.read"]
_jwks: dict = {"at": 0, "keys": None}


def bank_jwks() -> dict:
    """The bank's public keys, fetched from its jwks_uri and kept for five minutes."""
    if _jwks["keys"] is None or time.time() - _jwks["at"] > 300:
        _jwks["keys"] = httpx.get(f"{BANK_URL}/jwks.json", timeout=10).json()
        _jwks["at"] = time.time()
    return _jwks["keys"]


def log_check(outcome: str, who: str, reason: str) -> None:
    log = store.load("integration/mcp_token_checks.json", [])
    log.append({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "outcome": outcome, "who": who, "reason": reason})
    store.save("integration/mcp_token_checks.json", log[-200:])


class BankTokenVerifier:
    """Plugs ENG-801 into the MCP SDK: a valid token becomes an AccessToken carrying the person's Identity."""

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            ident = verify_access_token(token, bank_jwks(), BANK_ISSUER, MCP_RESOURCE, REQUIRED_SCOPES)
        except TokenRejected as e:
            log_check("refused", "", str(e))
            return None
        except NotImplementedError as e:
            log_check("refused", "", f"{e}: every token is refused until ENG-801 is built")
            return None
        log_check("accepted", ident.sub, f"via {ident.client_id}")
        return AccessToken(token=token, client_id=ident.client_id or "unknown", scopes=ident.scopes, expires_at=ident.expires_at,
                           resource=MCP_RESOURCE, subject=ident.sub, claims=ident.model_dump())


def current_identity() -> Identity:
    at = get_access_token()
    if at is None or not at.claims:
        raise ToolError("Not signed in")
    return Identity(**at.claims)


def _run(name: str, **kw) -> dict:
    try:
        return tools.TOOLS[name](current_identity(), **kw)
    except ToolRefused as e:
        raise ToolError(str(e))


mcp = FastMCP(
    name="kestrelmoor-kyc",
    instructions="Kestrelmoor Bank's CRM and KYC exceptions, as the signed-in member of staff. You only see what they may see.",
    host="127.0.0.1", port=int(MCP_URL.rsplit(":", 1)[-1].split("/")[0]),
    # No required_scopes here: clients then ask for no scope, and the bank grants what the person's role allows.
    # verify_access_token() still requires kyc.read on every request.
    auth=AuthSettings(issuer_url=BANK_ISSUER, resource_server_url=MCP_RESOURCE),
    token_verifier=BankTokenVerifier(),
)


@mcp.tool()
def find_customer(query: str = "") -> dict:
    """Search the bank's CRM by customer name or id (CU-…). An empty query lists every customer you may see."""
    return _run("find_customer", query=query)


@mcp.tool()
def get_customer(customer_id: str) -> dict:
    """One customer from the CRM: details, contact history and notes."""
    return _run("get_customer", customer_id=customer_id)


@mcp.tool()
def add_customer_note(customer_id: str, text: str) -> dict:
    """Add a note to a customer in the CRM, in your name."""
    return _run("add_customer_note", customer_id=customer_id, text=text)


@mcp.tool()
def list_exceptions(status: str = "") -> dict:
    """KYC exceptions you may see. status: open, in_progress, resolved, or empty for all."""
    return _run("list_exceptions", status=status)


@mcp.tool()
def get_exception(ticket_id: str) -> dict:
    """One KYC exception (KX-…) with its comments."""
    return _run("get_exception", ticket_id=ticket_id)


@mcp.tool()
def comment_on_exception(ticket_id: str, text: str) -> dict:
    """Add a comment to a KYC exception, in your name."""
    return _run("comment_on_exception", ticket_id=ticket_id, text=text)


@mcp.tool()
def assign_exception(ticket_id: str, analyst_id: str) -> dict:
    """Assign a KYC exception to an analyst in its team (team leads only)."""
    return _run("assign_exception", ticket_id=ticket_id, analyst_id=analyst_id)


@mcp.tool()
def list_documents(customer_id: str) -> dict:
    """The documents on a customer's file (CU-…), as metadata with no content. Only customers in your remit."""
    return _run("list_documents", customer_id=customer_id)


@mcp.tool()
def get_document(doc_id: str) -> dict:
    """One document (DS-…) with its content. The store allows 20 documents an hour per person: for checking a case, not bulk download."""
    return _run("get_document", doc_id=doc_id)


if __name__ == "__main__":
    port = int(os.getenv("FDE_MCP_PORT", mcp.settings.port))
    mcp.settings.port = port
    mcp.run(transport="streamable-http")
