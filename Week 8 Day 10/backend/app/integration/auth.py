"""Signing in to the console with the bank's sign-in service (done, not a ticket).

The console is an OAuth client ("fde-console"): Authorization Code with PKCE, asking for a token for the MCP server
(resource = MCP_RESOURCE). The browser only gets a session cookie; the token stays on the server.

sign_in_as() does the same flow without a browser, for the course's test accounts: the Act-as and Permissions tabs use it
to call the MCP server as Tom, Grace and Helen, exactly as their own sign-in would.
"""

import base64
import hashlib
import html
import re
import secrets
import time
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
import jwt

from app.config import BANK_URL, CONSOLE_CLIENT_ID, CONSOLE_CLIENT_SECRET, MCP_RESOURCE

COOKIE = "fde_session"
PASSWORD = "kyc-demo"  # the course accounts' password (shown on the bank's sign-in page)
_pending: dict[str, dict] = {}
_sessions: dict[str, dict] = {}
_test_tokens: dict[str, dict] = {}


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def login_url(redirect_uri: str, next_url: str = "/") -> str:
    verifier, challenge = _pkce()
    state = secrets.token_urlsafe(16)
    _pending[state] = {"verifier": verifier, "redirect_uri": redirect_uri, "next": next_url, "at": time.time()}
    return f"{BANK_URL}/authorize?" + urlencode({"response_type": "code", "client_id": CONSOLE_CLIENT_ID, "redirect_uri": redirect_uri,
                                                 "code_challenge": challenge, "code_challenge_method": "S256", "state": state,
                                                 "resource": MCP_RESOURCE})


def _exchange_code(code: str, verifier: str, redirect_uri: str) -> dict:
    r = httpx.post(f"{BANK_URL}/token", data={"grant_type": "authorization_code", "code": code, "code_verifier": verifier,
                                              "redirect_uri": redirect_uri, "resource": MCP_RESOURCE,
                                              "client_id": CONSOLE_CLIENT_ID, "client_secret": CONSOLE_CLIENT_SECRET}, timeout=10)
    r.raise_for_status()
    return r.json()


def _person(token: str) -> dict:
    # The token came straight from the bank's token endpoint, so the console can read it. The MCP server never trusts
    # a token this way: it checks every one (ENG-801).
    c = jwt.decode(token, options={"verify_signature": False})
    return {"sub": c["sub"], "name": c.get("name", ""), "role": c.get("role", ""), "team": c.get("team"), "region": c.get("region"),
            "scope": c.get("scope", ""), "expires_at": c.get("exp", 0), "client_id": c.get("client_id", "")}


def finish(code: str, state: str) -> tuple[str, str]:
    """Complete a browser sign-in. Returns (session id, where to go next)."""
    p = _pending.pop(state, None)
    if not p or time.time() - p["at"] > 600:
        raise ValueError("The sign-in took too long or was not started here: sign in again")
    tok = _exchange_code(code, p["verifier"], p["redirect_uri"])
    sid = secrets.token_urlsafe(24)
    _sessions[sid] = {"token": tok["access_token"], "refresh": tok.get("refresh_token"), "person": _person(tok["access_token"])}
    return sid, p["next"]


def session(sid: str | None) -> dict | None:
    s = _sessions.get(sid or "")
    if s and s["person"]["expires_at"] < time.time() + 30 and s.get("refresh"):
        r = httpx.post(f"{BANK_URL}/token", data={"grant_type": "refresh_token", "refresh_token": s["refresh"],
                                                  "client_id": CONSOLE_CLIENT_ID, "client_secret": CONSOLE_CLIENT_SECRET}, timeout=10)
        if r.status_code == 200:
            s.update(token=r.json()["access_token"], person=_person(r.json()["access_token"]))
        else:
            _sessions.pop(sid, None)
            return None
    return s


def sign_out(sid: str | None) -> None:
    _sessions.pop(sid or "", None)


def sign_in_as(user: str, http: httpx.Client | None = None) -> str:
    """A token for the MCP server for one of the course accounts, by the same Authorization Code + PKCE flow a browser follows."""
    cached = _test_tokens.get(user)
    if cached and cached["exp"] > time.time() + 60:
        return cached["token"]
    h = http or httpx.Client(timeout=10)
    redirect = "http://localhost:8000/api/auth/callback"
    verifier, challenge = _pkce()
    params = {"response_type": "code", "client_id": CONSOLE_CLIENT_ID, "redirect_uri": redirect, "code_challenge": challenge,
              "code_challenge_method": "S256", "state": "test", "resource": MCP_RESOURCE}
    page = h.get(f"{BANK_URL}/authorize", params=params)
    page.raise_for_status()
    fields = {k: html.unescape(v) for k, v in re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)"', page.text)}
    r = h.post(f"{BANK_URL}/authorize", data={**fields, "username": user, "password": PASSWORD}, follow_redirects=False)
    if r.status_code != 302:
        raise ValueError(f"Sign-in failed for {user}")
    code = parse_qs(urlparse(r.headers["location"]).query)["code"][0]
    t = h.post(f"{BANK_URL}/token", data={"grant_type": "authorization_code", "code": code, "code_verifier": verifier, "redirect_uri": redirect,
                                          "resource": MCP_RESOURCE, "client_id": CONSOLE_CLIENT_ID, "client_secret": CONSOLE_CLIENT_SECRET})
    t.raise_for_status()
    token = t.json()["access_token"]
    _test_tokens[user] = {"token": token, "exp": _person(token)["expires_at"]}
    return token
