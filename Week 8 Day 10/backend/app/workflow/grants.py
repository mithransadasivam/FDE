"""Day 10: who the workflow acts as, for days (done, not a ticket).

A person's token lasts 15 minutes; a case can wait two weeks for an applicant. So when Tom starts a case workflow, the console
asks the bank to let the workflow worker act for him on that one case: a token exchange that asks for a refresh token
(RFC 8693), from the client fde-workflow. The bank keeps the grant. It lasts 14 days, or until the workflow revokes it when the
case ends.

Each step swaps the grant for a fresh 15-minute token. Every system then sees Tom, acted for by fde-workflow, and applies
Tom's rules: his remit, his scopes. The audit says "tom.reyes via fde-mcp, for fde-workflow".

The grant itself is a secret. It is kept here, in engagement/workflow/grants.json, standing in for the bank's secret store;
the workflow's inputs and steps, saved in the DBOS database, only ever carry the ticket id.
"""

import threading
import time

import httpx

from app import store
from app.config import BANK_URL, MCP_RESOURCE, WORKFLOW_CLIENT_ID, WORKFLOW_CLIENT_SECRET
from app.integration.downstream import ACCESS_TOKEN, TOKEN_EXCHANGE
from app.integration.models import Identity, ToolRefused

REFRESH_TOKEN = "urn:ietf:params:oauth:token-type:refresh_token"
_lock = threading.RLock()
_jwks: dict = {"at": 0, "keys": None}


def _creds() -> dict:
    return {"client_id": WORKFLOW_CLIENT_ID, "client_secret": WORKFLOW_CLIENT_SECRET}


def _why(r: httpx.Response) -> str:
    try:
        return r.json().get("error_description", r.text)
    except ValueError:
        return r.text


def open_grant(identity: Identity, ticket_id: str, key: str) -> None:
    """Tom delegates one case to the workflow worker. `key` names the workflow (one grant per workflow)."""
    r = httpx.post(f"{BANK_URL}/token", timeout=10, data={
        "grant_type": TOKEN_EXCHANGE, "subject_token": identity.token, "subject_token_type": ACCESS_TOKEN,
        "requested_token_type": REFRESH_TOKEN, "resource": f"case:{ticket_id}", **_creds()})
    if r.status_code != 200:
        raise ToolRefused(f"The bank would not let the workflow act for {identity.sub} on {ticket_id}: {_why(r)}")
    with _lock:
        g = store.load("workflow/grants.json", {})
        g[key] = {"grant": r.json()["access_token"], "person": identity.sub, "ticket_id": ticket_id, "at": time.time()}
        store.save("workflow/grants.json", g)


def _grant(key: str) -> str:
    g = store.load("workflow/grants.json", {}).get(key)
    if not g:
        raise ToolRefused(f"No case grant for {key}: start the case again from the console")
    return g["grant"]


def token_for(key: str, audience: str) -> str:
    """A fresh 15-minute token for one of the bank's systems, as the person who started the workflow."""
    r = httpx.post(f"{BANK_URL}/token", timeout=10, data={"grant_type": "refresh_token", "refresh_token": _grant(key),
                                                          "resource": audience, **_creds()})
    if r.status_code != 200:
        raise ToolRefused(f"The sign-in service refused the case grant: {_why(r)}")
    return r.json()["access_token"]


def identity(key: str) -> Identity:
    """The person, as the tools need them (Day 8): a checked token for the MCP server, from the case grant."""
    from app.integration.tokens import verify_access_token
    from app.config import BANK_ISSUER

    if _jwks["keys"] is None or time.time() - _jwks["at"] > 300:
        _jwks["keys"] = httpx.get(f"{BANK_URL}/jwks.json", timeout=10).json()
        _jwks["at"] = time.time()
    return verify_access_token(token_for(key, MCP_RESOURCE), _jwks["keys"], BANK_ISSUER, MCP_RESOURCE, ["kyc.read"])


def close_grant(key: str) -> None:
    """The case is over: the workflow gives the grant back (RFC 7009), so it can never be used again."""
    rec = store.load("workflow/grants.json", {}).get(key)
    if not rec:
        return
    httpx.post(f"{BANK_URL}/revoke", timeout=10, data={"token": rec["grant"], **_creds()})  # revoking twice is harmless
    with _lock:
        g = store.load("workflow/grants.json", {})
        g.pop(key, None)
        store.save("workflow/grants.json", g)
