"""The bank's sign-in service: an OAuth 2.1 authorization server with OpenID-style metadata (done, not a ticket).

    /.well-known/oauth-authorization-server   where everything is (RFC 8414)
    /jwks.json                               the public key that checks every token
    /register                                a client registers itself (RFC 7591): how Claude Code signs up
    /authorize                               the sign-in page; returns a code (PKCE S256 required)
    /token                                   code -> token, refresh, client credentials, token exchange (RFC 8693)

Access tokens are JWTs signed RS256, valid for 15 minutes, for one resource (the `aud` claim, RFC 8707).
"""

import base64
import hashlib
import html
import secrets
import time
from urllib.parse import urlencode, urlparse

import jwt
from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from bank import core

router = APIRouter()
_codes: dict[str, dict] = {}
_refresh: dict[str, dict] = {}
TOKEN_EXCHANGE = "urn:ietf:params:oauth:grant-type:token-exchange"
ACCESS_TOKEN_TYPE = "urn:ietf:params:oauth:token-type:access_token"


def _err(error: str, desc: str, status: int = 400):
    return JSONResponse({"error": error, "error_description": desc}, status_code=status)


@router.get("/.well-known/oauth-authorization-server")
@router.get("/.well-known/openid-configuration")
def metadata():
    b = core.BANK_URL
    return {"issuer": core.ISSUER, "authorization_response_iss_parameter_supported": True, "authorization_endpoint": f"{b}/authorize", "token_endpoint": f"{b}/token",
            "registration_endpoint": f"{b}/register", "jwks_uri": f"{b}/jwks.json", "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token", "client_credentials", TOKEN_EXCHANGE],
            "code_challenge_methods_supported": ["S256"], "scopes_supported": ["kyc.read", "kyc.write", "kyc.assign"],
            "token_endpoint_auth_methods_supported": ["none", "client_secret_post", "client_secret_basic"]}


@router.get("/jwks.json")
def jwks():
    return core.jwks()


# ---------------------------------------------------------------- clients
def _clients() -> dict:
    return {**{k: {**v} for k, v in core.CLIENTS.items()}, **core.load("clients.json", {})}


@router.post("/register", status_code=201)
async def register(request: Request):
    body = await request.json()
    uris = body.get("redirect_uris") or []
    if not uris or not all(_loopback(u) for u in uris):
        return _err("invalid_redirect_uri", "Redirect URIs must be http://localhost or 127.0.0.1 on this course server")
    cid = "dyn-" + secrets.token_hex(6)
    method = body.get("token_endpoint_auth_method", "none")
    rec = {"name": body.get("client_name", cid), "redirect_uris": uris, "grants": body.get("grant_types") or ["authorization_code", "refresh_token"],
           "auth_method": method}
    out = {**body, "client_id": cid, "client_id_issued_at": int(time.time()), "token_endpoint_auth_method": method,
           "grant_types": rec["grants"], "response_types": ["code"]}
    if method != "none":
        rec["secret"] = secrets.token_urlsafe(24)
        out["client_secret"] = rec["secret"]
    saved = core.load("clients.json", {})
    saved[cid] = rec
    core.save("clients.json", saved)
    return out


def _loopback(uri: str) -> bool:
    u = urlparse(uri)
    return u.scheme == "http" and u.hostname in ("localhost", "127.0.0.1")


def _redirect_ok(client: dict, uri: str) -> bool:
    if client.get("redirect") == "loopback":
        return _loopback(uri)
    return uri in client.get("redirect_uris", [])


def _client_auth(request_form: dict, auth_header: str) -> tuple[str, dict] | None:
    """The client and its record, if it authenticated (or is public). None if it failed."""
    cid, secret = request_form.get("client_id"), request_form.get("client_secret")
    if auth_header.lower().startswith("basic "):
        cid, _, secret = base64.b64decode(auth_header[6:]).decode().partition(":")
    client = _clients().get(cid or "")
    if not client:
        return None
    if client.get("secret") and not secrets.compare_digest(client["secret"], secret or ""):
        return None
    return cid, client


# ---------------------------------------------------------------- sign-in
PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Kestrelmoor Bank · Sign in</title>
<meta name="viewport" content="width=device-width, initial-scale=1"><style>
body{{font-family:Inter,system-ui,sans-serif;background:#1B1F3B;color:#1B1F3B;display:grid;place-items:center;min-height:100vh;margin:0}}
.card{{background:#fff;border-radius:16px;padding:32px 36px;width:380px;box-shadow:0 10px 40px rgba(0,0,0,.25)}}
h1{{font-size:20px;margin:0 0 4px}} .sub{{color:#5E6378;font-size:13px;margin-bottom:20px}}
label{{display:block;font-size:12px;font-weight:600;color:#5E6378;margin:12px 0 4px}}
input,select{{width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid #d8dae5;border-radius:8px;font-size:14px}}
button{{margin-top:20px;width:100%;padding:11px;border:0;border-radius:8px;background:#0E8F7E;color:#fff;font-weight:600;font-size:14px}}
.app{{background:#F4F5FA;border-radius:8px;padding:10px 12px;font-size:12.5px;margin-bottom:6px}} .err{{color:#E8552F;font-size:13px;margin-top:10px}}
.hint{{color:#9A9EB3;font-size:11.5px;margin-top:14px}}</style></head><body><form class="card" method="post" action="/authorize">
<h1>Kestrelmoor Bank</h1><div class="sub">Staff sign-in</div>
<div class="app"><b>{app}</b> asks to act as you{res}.<br>Permissions: {scopes}</div>
<label for="username">User</label><select id="username" name="username">{options}</select>
<label for="password">Password</label><input id="password" name="password" type="password" autocomplete="current-password">
{hidden}<button id="signin" type="submit">Sign in and allow</button>{error}
<div class="hint">Course accounts: tom.reyes, grace.mensah, helen.achebe · password {pw}</div></form></body></html>"""


def _page(params: dict, client: dict, error: str = "") -> HTMLResponse:
    hidden = "".join(f'<input type="hidden" name="{k}" value="{html.escape(v)}">' for k, v in params.items() if v)
    opts = "".join(f'<option value="{u}">{p["name"]} · {u}</option>' for u, p in core.PEOPLE.items())
    res = f" on <b>{html.escape(params.get('resource', ''))}</b>" if params.get("resource") else ""
    return HTMLResponse(PAGE.format(app=html.escape(client.get("name", params.get("client_id", ""))), res=res, options=opts, hidden=hidden,
                                    scopes=html.escape(params.get("scope") or "kyc.read kyc.write"), pw=core.PASSWORD,
                                    error=f'<div class="err" id="signin-error">{html.escape(error)}</div>' if error else ""))


_FIELDS = ["response_type", "client_id", "redirect_uri", "code_challenge", "code_challenge_method", "state", "scope", "resource"]


def _check(params: dict):
    client = _clients().get(params.get("client_id", ""))
    if not client:
        raise HTTPException(400, "Unknown client_id")
    if not _redirect_ok(client, params.get("redirect_uri", "")):
        raise HTTPException(400, "This redirect_uri is not registered for the client")
    if params.get("response_type") != "code" or params.get("code_challenge_method") != "S256" or not params.get("code_challenge"):
        raise HTTPException(400, "Use response_type=code with a PKCE code_challenge (S256)")
    return client


@router.get("/authorize")
def authorize_page(request: Request):
    params = {k: request.query_params.get(k, "") for k in _FIELDS}
    return _page(params, _check(params))


@router.post("/authorize")
async def authorize_submit(request: Request):
    form = dict(await request.form())
    params = {k: form.get(k, "") for k in _FIELDS}
    client = _check(params)
    user = form.get("username", "")
    if user not in core.PEOPLE or not secrets.compare_digest(form.get("password", ""), core.PASSWORD):
        return _page(params, client, "Wrong user or password")
    code = secrets.token_urlsafe(24)
    _codes[code] = {**params, "sub": user, "at": time.time()}
    q = {"code": code, **({"state": params["state"]} if params["state"] else {}), "iss": core.ISSUER}  # RFC 9207
    return RedirectResponse(params["redirect_uri"] + ("&" if "?" in params["redirect_uri"] else "?") + urlencode(q), status_code=302)


# ---------------------------------------------------------------- tokens
def _scopes(sub: str, requested: str | None) -> list[str]:
    allowed = core.PEOPLE.get(sub, {}).get("scopes") or core.CLIENTS.get(sub, {}).get("scopes", [])
    if not requested:
        return allowed
    return [s for s in requested.split() if s in allowed]


def _token_response(sub: str, audience: str, scopes: list[str], client_id: str, refresh: bool, act: dict | None = None, lifetime: int = 900):
    out = {"access_token": core.issue(sub, audience, scopes, client_id, lifetime=lifetime, act=act), "token_type": "Bearer",
           "expires_in": lifetime, "scope": " ".join(scopes)}
    if refresh:
        rt = secrets.token_urlsafe(32)
        _refresh[rt] = {"sub": sub, "aud": audience, "scopes": scopes, "client_id": client_id}
        out["refresh_token"] = rt
    if act is not None:
        out["issued_token_type"] = ACCESS_TOKEN_TYPE
    return out


@router.post("/token")
async def token(request: Request):
    form = dict(await request.form())
    auth = _client_auth(form, request.headers.get("authorization", ""))
    if auth is None:
        return _err("invalid_client", "Unknown client or wrong secret", 401)
    cid, client = auth
    grant = form.get("grant_type", "")
    if grant == "authorization_code":
        c = _codes.pop(form.get("code", ""), None)
        if not c or c["client_id"] != cid or time.time() - c["at"] > 120:
            return _err("invalid_grant", "The code is unknown, used or expired")
        if form.get("redirect_uri") and form["redirect_uri"] != c["redirect_uri"]:
            return _err("invalid_grant", "redirect_uri does not match")
        challenge = base64.urlsafe_b64encode(hashlib.sha256(form.get("code_verifier", "").encode()).digest()).rstrip(b"=").decode()
        if not secrets.compare_digest(challenge, c["code_challenge"]):
            return _err("invalid_grant", "PKCE check failed")
        aud = form.get("resource") or c.get("resource") or core.MCP_RESOURCE
        return _token_response(c["sub"], aud, _scopes(c["sub"], c.get("scope")), cid, refresh=True)
    if grant == "refresh_token":
        r = _refresh.get(form.get("refresh_token", ""))
        if not r or r["client_id"] != cid:
            return _err("invalid_grant", "Unknown refresh token")
        return _token_response(r["sub"], r["aud"], r["scopes"], cid, refresh=False)
    if grant == "client_credentials" and "client_credentials" in client.get("grants", []):
        aud = form.get("resource") or form.get("audience") or ""
        if aud not in core.RESOURCES:
            return _err("invalid_target", f"Unknown resource {aud!r}")
        return _token_response(cid, aud, _scopes(cid, form.get("scope")), cid, refresh=False)
    if grant == TOKEN_EXCHANGE and TOKEN_EXCHANGE in client.get("grants", []):
        aud = form.get("audience") or form.get("resource") or ""
        if aud not in core.RESOURCES:
            return _err("invalid_target", f"Unknown audience {aud!r}")
        try:
            subj = core.verify(form.get("subject_token", ""), core.MCP_RESOURCE)
        except jwt.PyJWTError as e:
            return _err("invalid_grant", f"The subject token is not valid for {core.MCP_RESOURCE}: {e}")
        lifetime = max(1, min(900, int(subj["exp"] - time.time())))
        return _token_response(subj["sub"], aud, subj.get("scope", "").split(), cid, refresh=False, act={"sub": cid}, lifetime=lifetime)
    return _err("unsupported_grant_type", f"{grant or 'no grant_type'} is not allowed for {cid}")
