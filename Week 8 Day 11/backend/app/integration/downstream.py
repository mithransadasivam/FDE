"""Ticket ENG-802: call the bank's systems as the person, not as the console.

When Tom asks the MCP server for a customer, the MCP server calls the bank's CRM. Which token does it send?

  - Not Tom's own token: it was issued for the MCP server (aud = http://localhost:8200/mcp), and the MCP specification forbids
    passing a client's token through to another system ("token passthrough").
  - Not the console's service account: the CRM would see "svc-fde-console", show every team's customers, and the audit
    could never say who asked.
  - A new token for the CRM, issued to Tom, which says the MCP server acts for him: OAuth 2.0 Token Exchange (RFC 8693).
    The bank's sign-in service checks Tom's token and returns one with aud = "crm", sub = "tom.reyes", his scopes,
    and act = {"sub": "fde-mcp"}.
"""

import httpx

from app.config import BANK_URL, MCP_CLIENT_ID, MCP_CLIENT_SECRET, SERVICE_CLIENT_ID, SERVICE_CLIENT_SECRET
from app.integration.models import Identity, ToolRefused

TOKEN_EXCHANGE = "urn:ietf:params:oauth:grant-type:token-exchange"
ACCESS_TOKEN = "urn:ietf:params:oauth:token-type:access_token"


def service_account_token(audience: str, http: httpx.Client) -> str:
    """The console's own service account (client credentials). Every call looks like the console, with access to everything."""
    r = http.post(f"{BANK_URL}/token", data={"grant_type": "client_credentials", "client_id": SERVICE_CLIENT_ID,
                                              "client_secret": SERVICE_CLIENT_SECRET, "resource": audience})
    if r.status_code != 200:
        raise ToolRefused(f"The sign-in service refused the service account: {r.text[:200]}")
    return r.json()["access_token"]


def downstream_token(identity: Identity, audience: str, http: httpx.Client) -> str:
    """A token to call one of the bank's systems (`audience`: "crm", "kyc-exceptions" or "documents") as `identity`.

    Exchange the person's token at the bank's token endpoint (f"{BANK_URL}/token"), as a form post:
        grant_type          TOKEN_EXCHANGE
        subject_token       identity.token
        subject_token_type  ACCESS_TOKEN
        audience            audience
        client_id / client_secret   MCP_CLIENT_ID / MCP_CLIENT_SECRET (the MCP server authenticates itself)
    Return the "access_token" from the JSON reply. If the reply is not 200, raise
    ToolRefused("The sign-in service refused the exchange: <its error_description>").
    Never return identity.token itself, and never use service_account_token().
    """
    r = http.post(f"{BANK_URL}/token", data={"grant_type": TOKEN_EXCHANGE, "subject_token": identity.token, "subject_token_type": ACCESS_TOKEN,
                                              "audience": audience, "client_id": MCP_CLIENT_ID, "client_secret": MCP_CLIENT_SECRET})
    if r.status_code != 200:
        try:
            why = r.json().get("error_description", r.text)
        except ValueError:
            why = r.text
        raise ToolRefused(f"The sign-in service refused the exchange: {why}")
    return r.json()["access_token"]
