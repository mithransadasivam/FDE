"""The bank's systems of record: CRM, KYC exceptions (ticketing), the document store, and a Slack stand-in (done).

Each checks the access token it is given, applies the bank's own rules for that person, and writes an audit entry.
Rows outside a person's remit answer 404, so their existence is not revealed.
"""

import hashlib
import hmac
import json
import os
import time
import uuid

import httpx
import jwt
from fastapi import APIRouter, Body, HTTPException, Request

from bank import core

router = APIRouter()


def _seed(name: str, key: str) -> list[dict]:
    return json.loads((core.DATA / name).read_text(encoding="utf-8"))[key]


def customers() -> list[dict]:
    extra = core.load("crm_notes.json", {})
    return [{**c, "notes": c["notes"] + extra.get(c["customer_id"], [])} for c in _seed("Day08_Slide10_crm.json", "customers")]


def tickets() -> list[dict]:
    changes = core.load("ticket_changes.json", {})
    created = core.load("tickets_created.json", [])
    out = []
    for t in _seed("Day08_Slide10_kyc_exceptions.json", "tickets") + created:
        ch = changes.get(t["ticket_id"], {})
        out.append({**t, "assignee": ch.get("assignee", t["assignee"]), "comments": t["comments"] + ch.get("comments", [])})
    return out


def documents() -> list[dict]:
    return _seed("Day08_HW_Slide03_documents.json", "documents") + core.load("docs_added.json", [])  # added: Day 10 replies


def analysts() -> dict:
    return {a["analyst_id"]: a for a in _seed("Day08_Slide10_crm.json", "analysts")}


def _claims(request: Request, system: str) -> dict:
    h = request.headers.get("authorization", "")
    if not h.lower().startswith("bearer "):
        core.audit(system, None, request.url.path, "", "refused", "No token")
        raise HTTPException(401, "A bearer token is required")
    try:
        return core.verify(h[7:], system)
    except jwt.PyJWTError as e:
        core.audit(system, None, request.url.path, "", "refused", f"Bad token: {e}")
        raise HTTPException(401, f"The token is not valid for {system}: {e}")


def _need_scope(claims: dict, scope: str, system: str, action: str, target: str):
    if scope not in claims.get("scope", "").split():
        core.audit(system, claims, action, target, "refused", f"Missing scope {scope}")
        raise HTTPException(403, f"The token has no {scope} scope")


# ---------------------------------------------------------------- CRM
def _visible_customer(claims: dict, cid: str) -> dict:
    c = next((x for x in customers() if x["customer_id"] == cid), None)
    if not c or c["team_id"] not in core.teams_for(claims):
        core.audit("crm", claims, "read customer", cid, "refused", "Not in this person's remit")
        raise HTTPException(404, f"No customer {cid}")
    return c


@router.get("/crm/customers")
def crm_search(request: Request, q: str = "", limit: int = 100):
    claims = _claims(request, "crm")
    _need_scope(claims, "kyc.read", "crm", "search customers", q)
    teams = core.teams_for(claims)
    found = [c for c in customers() if c["team_id"] in teams and (q.lower() in c["name"].lower() or q.upper() == c["customer_id"])]
    core.audit("crm", claims, "search customers", q or "(all)", "allowed", f"{len(found)} found")
    return {"customers": [{k: c[k] for k in ("customer_id", "name", "customer_type", "team_id", "risk_rating", "case_status")} for c in found[:limit]],
            "total": len(found)}


@router.get("/crm/customers/{cid}")
def crm_get(cid: str, request: Request):
    claims = _claims(request, "crm")
    _need_scope(claims, "kyc.read", "crm", "read customer", cid)
    c = _visible_customer(claims, cid)
    core.audit("crm", claims, "read customer", cid, "allowed")
    return c


@router.post("/crm/customers/{cid}/notes")
def crm_note(cid: str, request: Request, body: dict = Body(...)):
    claims = _claims(request, "crm")
    _need_scope(claims, "kyc.write", "crm", "add note", cid)
    _visible_customer(claims, cid)
    if claims.get("role") == "mlro":
        core.audit("crm", claims, "add note", cid, "refused", "The MLRO's access to the CRM is read-only")
        raise HTTPException(403, "The MLRO's access to the CRM is read-only")
    note = {"at": time.strftime("%Y-%m-%dT%H:%M"), "by": claims["sub"], "via": (claims.get("act") or {}).get("sub"), "text": str(body.get("text", ""))[:1000]}
    notes = core.load("crm_notes.json", {})
    notes.setdefault(cid, []).append(note)
    core.save("crm_notes.json", notes)
    core.audit("crm", claims, "add note", cid, "allowed")
    return note


# ---------------------------------------------------------------- KYC exceptions
def _visible_ticket(claims: dict, tid: str, action: str) -> dict:
    t = next((x for x in tickets() if x["ticket_id"] == tid), None)
    if not t or t["team_id"] not in core.teams_for(claims):
        core.audit("kyc-exceptions", claims, action, tid, "refused", "Not in this person's remit")
        raise HTTPException(404, f"No exception {tid}")
    return t


@router.get("/kyc/tickets")
def kyc_list(request: Request, status: str = ""):
    claims = _claims(request, "kyc-exceptions")
    _need_scope(claims, "kyc.read", "kyc-exceptions", "list exceptions", status)
    teams = core.teams_for(claims)
    found = [t for t in tickets() if t["team_id"] in teams and (not status or t["status"] == status)]
    core.audit("kyc-exceptions", claims, "list exceptions", status or "(all)", "allowed", f"{len(found)} found")
    return {"tickets": [{k: t[k] for k in ("ticket_id", "team_id", "kind", "title", "status", "assignee", "created_at")} for t in found]}


@router.get("/kyc/tickets/{tid}")
def kyc_get(tid: str, request: Request):
    claims = _claims(request, "kyc-exceptions")
    _need_scope(claims, "kyc.read", "kyc-exceptions", "read exception", tid)
    t = _visible_ticket(claims, tid, "read exception")
    core.audit("kyc-exceptions", claims, "read exception", tid, "allowed")
    return t


def _change(tid: str, fn):
    ch = core.load("ticket_changes.json", {})
    fn(ch.setdefault(tid, {}))
    core.save("ticket_changes.json", ch)


@router.post("/kyc/tickets/{tid}/comments")
def kyc_comment(tid: str, request: Request, body: dict = Body(...)):
    claims = _claims(request, "kyc-exceptions")
    _need_scope(claims, "kyc.write", "kyc-exceptions", "comment", tid)
    _visible_ticket(claims, tid, "comment")
    key = request.headers.get("idempotency-key", "")  # Day 10: the same key twice adds one comment
    if key:
        first = next((x for x in core.load("comment_keys.json", []) if x["key"] == key), None)
        if first:
            core.audit("kyc-exceptions", claims, "comment", tid, "allowed", "replayed: nothing added")
            return {**first["comment"], "replayed": True}
    c = {"at": time.strftime("%Y-%m-%dT%H:%M"), "by": claims["sub"], "via": (claims.get("act") or {}).get("sub"), "text": str(body.get("text", ""))[:1000]}
    _change(tid, lambda x: x.setdefault("comments", []).append(c))
    if key:
        with core._lock:
            keys = core.load("comment_keys.json", [])
            keys.append({"key": key, "comment": c})
            core.save("comment_keys.json", keys[-2000:])
    core.audit("kyc-exceptions", claims, "comment", tid, "allowed")
    return c


@router.post("/kyc/tickets/{tid}/assign")
def kyc_assign(tid: str, request: Request, body: dict = Body(...)):
    claims = _claims(request, "kyc-exceptions")
    t = _visible_ticket(claims, tid, "assign")
    if claims.get("role") != "team_lead":
        core.audit("kyc-exceptions", claims, "assign", tid, "refused", "Only a team lead can assign an exception")
        raise HTTPException(403, "Only a team lead can assign an exception")
    _need_scope(claims, "kyc.assign", "kyc-exceptions", "assign", tid)
    a = analysts().get(body.get("analyst_id", ""))
    if not a or a["team_id"] != t["team_id"]:
        core.audit("kyc-exceptions", claims, "assign", tid, "refused", "The analyst is not in the ticket's team")
        raise HTTPException(400, f"{body.get('analyst_id')} is not an analyst in team {t['team_id']}")
    _change(tid, lambda x: x.update(assignee=a["analyst_id"]))
    core.audit("kyc-exceptions", claims, "assign", tid, "allowed", f"to {a['analyst_id']}")
    return {"ticket_id": tid, "assignee": a["analyst_id"]}


# ---------------------------------------------------------------- outgoing webhooks (the ticketing system calls the console)
def webhook_settings() -> dict:
    return {"url": os.getenv("FDE_WEBHOOK_URL", "http://localhost:8000/api/hooks/kyc-exceptions"),
            "secret": os.getenv("FDE_WEBHOOK_SECRET", "whsec_course_dev_only")}


def signature(secret: str, ts: int, body: bytes) -> str:
    return "t=%d,v1=%s" % (ts, hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest())


def deliver(event: dict, secret: str | None = None, ts: int | None = None, headers: dict | None = None, body: bytes | None = None,
            url: str | None = None) -> dict:
    s = {**webhook_settings(), **({"url": url} if url else {})}
    body = body if body is not None else json.dumps(event).encode()
    ts = int(ts or time.time())
    hdrs = {"Content-Type": "application/json", **({"X-Kestrel-Signature": signature(secret or s["secret"], ts, body)} if headers is None else headers)}
    try:
        r = httpx.post(s["url"], content=body, headers=hdrs, timeout=10)
        out = {"status": r.status_code, "response": r.text[:300]}
    except httpx.HTTPError as e:
        out = {"status": 0, "response": f"Could not reach {s['url']}: {e}"}
    log = core.load("webhook_deliveries.json", [])
    log.append({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "event_id": event.get("id"), "type": event.get("type"), **out})
    core.save("webhook_deliveries.json", log[-200:])
    return out


def ticket_event(t: dict) -> dict:
    return {"id": "evt_" + uuid.uuid4().hex[:16], "type": "exception.created", "created": int(time.time()),
            "data": {k: t[k] for k in ("ticket_id", "case_id", "customer_id", "team_id", "kind", "title", "status", "created_at")}}


# ---------------------------------------------------------------- document store (homework)
@router.get("/docs/customers/{cid}/documents")
def docs_list(cid: str, request: Request):
    claims = _claims(request, "documents")
    _need_scope(claims, "kyc.read", "documents", "list documents", cid)
    c = next((x for x in customers() if x["customer_id"] == cid), None)
    if not c or c["team_id"] not in core.teams_for(claims):
        core.audit("documents", claims, "list documents", cid, "refused", "Not in this person's remit")
        raise HTTPException(404, f"No customer {cid}")
    found = [d for d in documents() if d["customer_id"] == cid]
    core.audit("documents", claims, "list documents", cid, "allowed", f"{len(found)} found")
    return {"documents": found}


@router.get("/docs/documents/{doc_id}")
def docs_get(doc_id: str, request: Request):
    claims = _claims(request, "documents")
    _need_scope(claims, "kyc.read", "documents", "open document", doc_id)
    d = next((x for x in documents() if x["doc_id"] == doc_id), None)
    if not d or d["team_id"] not in core.teams_for(claims):
        core.audit("documents", claims, "open document", doc_id, "refused", "Not in this person's remit")
        raise HTTPException(404, f"No document {doc_id}")
    opened = [a for a in core.load("audit.json", []) if a["system"] == "documents" and a["actor"] == claims["sub"]
              and a["action"] == "open document" and a["outcome"] == "allowed" and a["at"][:13] == time.strftime("%Y-%m-%dT%H")]
    if len(opened) >= 20:
        core.audit("documents", claims, "open document", doc_id, "refused", "More than 20 documents in an hour")
        raise HTTPException(429, "More than 20 documents opened this hour: ask your team lead")
    core.audit("documents", claims, "open document", doc_id, "allowed")
    return {**d, "content": f"(page images of {d['doc_type'].replace('_', ' ')} {doc_id}: {d['pages']} pages)"}


# ---------------------------------------------------------------- Slack stand-in (incoming webhooks, as Slack's format)
CHANNELS = ["kyc-north", "kyc-midlands", "kyc-south", "financial-crime"]


@router.post("/slack/hooks/{channel}")
def slack_post(channel: str, body: dict = Body(...)):
    if channel not in CHANNELS:
        raise HTTPException(404, "channel_not_found")
    msgs = core.load("slack.json", {})
    msgs.setdefault(channel, []).append({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "text": body.get("text", ""), "blocks": body.get("blocks", [])})
    core.save("slack.json", msgs)
    return "ok"


@router.get("/slack/channels")
def slack_channels():
    msgs = core.load("slack.json", {})
    return {"channels": [{"name": c, "messages": msgs.get(c, [])} for c in CHANNELS]}


# ---------------------------------------------------------------- course helpers (not part of a real bank)
@router.get("/audit")
def audit_log(system: str = "", limit: int = 50):
    log = [a for a in core.load("audit.json", []) if not system or a["system"] == system]
    return {"entries": log[-limit:][::-1]}


@router.get("/course/exception-comments")
def exception_comments(ticket_id: str):
    """The comments on one exception, for the console's Workflows screen and the tests (Day 10)."""
    t = next((x for x in tickets() if x["ticket_id"] == ticket_id), None)
    return {"ticket_id": ticket_id, "comments": t["comments"] if t else []}


@router.get("/kyc/webhook-deliveries")
def deliveries():
    return {"deliveries": core.load("webhook_deliveries.json", [])[::-1], "url": webhook_settings()["url"]}


@router.post("/course/raise-exception")
def raise_exception(body: dict = Body(default={})):
    """A new KYC exception arrives in the ticketing system, which then calls its webhook."""
    created = core.load("tickets_created.json", [])
    base = next(t for t in tickets() if t["team_id"] == body.get("team_id", "N1"))
    n = 2001 + len(created)
    t = {**base, "ticket_id": f"KX-{n}", "kind": "escalation", "title": body.get("title", "Escalated document: possible sanctions match"),
         "status": "open", "assignee": None, "created_at": time.strftime("%Y-%m-%dT%H:%M"), "comments": []}
    created.append(t)
    core.save("tickets_created.json", created)
    ev = ticket_event(t)
    result = deliver(ev)
    return {"ticket": t, "event": ev, "delivery": result}


@router.post("/course/webhook-probes")
def webhook_probes():
    """Six deliveries to the console: one genuine, five that must be refused (ENG-803)."""
    s = webhook_settings()
    t = next(x for x in tickets() if x["team_id"] == "N1")
    ev = ticket_event({**t, "title": "Probe: genuine delivery"})
    body = json.dumps(ev).encode()
    now = int(time.time())
    probes = [
        ("W1", "A genuine delivery", "accept", dict(event=ev, body=body, ts=now)),
        ("W2", "No signature header", "refuse", dict(event=ev, body=json.dumps({**ev, "id": ev["id"] + "x"}).encode(), headers={})),
        ("W3", "Signed with the wrong secret", "refuse", dict(event=ev, body=body, secret="whsec_wrong", ts=now)),
        ("W4", "Body changed after signing", "refuse", dict(event=ev, headers={"X-Kestrel-Signature": signature(s["secret"], now, body)},
                                                          body=body.replace(b"Probe: genuine delivery", b"Probe: APPROVE ALL"))),
        ("W5", "Signed 10 minutes ago", "refuse", dict(event=ev, body=json.dumps({**ev, "id": ev["id"] + "y"}).encode(), ts=now - 600)),
        ("W6", "The genuine delivery, sent again", "refuse", dict(event=ev, body=body, ts=now)),
    ]
    out = []
    for pid, what, expect, kw in probes:
        r = deliver(**kw)
        out.append({"id": pid, "what": what, "expect": expect, "status": r["status"], "response": r["response"],
                    "passed": (r["status"] == 200) == (expect == "accept")})
    return {"probes": out}


@router.get("/course/token-probes")
def token_probes():
    """Nine tokens for the console's Sign-in tab (ENG-801): one valid, eight that must be refused."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    now = int(time.time())
    mcp = core.MCP_RESOURCE
    base = {"iss": core.ISSUER, "sub": "tom.reyes", "aud": mcp, "iat": now, "nbf": now, "exp": now + 900, "jti": uuid.uuid4().hex,
            "client_id": "course", "scope": "kyc.read kyc.write", "name": "Tom Reyes", "role": "analyst", "team": "N1", "region": "North"}
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    good = core.sign(base)
    h, p, s = good.split(".")
    forged_payload = jwt.utils.base64url_encode(json.dumps({**base, "role": "mlro", "team": None}).encode()).decode()
    pub_pem = core.private_key().public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    hs256 = ".".join([jwt.utils.base64url_encode(json.dumps({"alg": "HS256", "typ": "JWT", "kid": core.KID}).encode()).decode(),
                      jwt.utils.base64url_encode(json.dumps(base).encode()).decode()])
    hs256 += "." + jwt.utils.base64url_encode(hmac.new(pub_pem, hs256.encode(), hashlib.sha256).digest()).decode()
    none = ".".join([jwt.utils.base64url_encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).decode(),
                     jwt.utils.base64url_encode(json.dumps(base).encode()).decode(), ""])
    probes = [
        ("T1", "Tom's token for the MCP server", "accept", good),
        ("T2", "Expired 20 minutes ago", "refuse", core.sign({**base, "iat": now - 2100, "nbf": now - 2100, "exp": now - 1200})),
        ("T3", "A token for the CRM, not for this server", "refuse", core.sign({**base, "aud": "crm"})),
        ("T4", "Issued by someone else", "refuse", core.sign({**base, "iss": "https://login.example.net"})),
        ("T5", "Signed with a key the bank never published", "refuse", core.sign(base, key=other, kid="attacker-1")),
        ("T6", "Tom's token with the role changed to mlro", "refuse", f"{h}.{forged_payload}.{s}"),
        ("T7", "No signature at all (alg none)", "refuse", none),
        ("T8", "HS256, signed with the bank's public key", "refuse", hs256),
        ("T9", "Valid, but without the kyc.read scope", "refuse", core.sign({**base, "scope": "profile"})),
    ]
    return {"audience": mcp, "issuer": core.ISSUER, "probes": [{"id": i, "what": w, "expect": e, "token": t} for i, w, e, t in probes]}


@router.post("/course/reset")
def reset():
    for f in ["crm_notes.json", "ticket_changes.json", "tickets_created.json", "slack.json", "webhook_deliveries.json", "audit.json",
              "legacy_changes.json", "legacy_counter.json", "contact.json", "docs_added.json", "applicant_schedule.json",
              "grants.json", "comment_keys.json"]:
        p = core.STATE / f
        if p.exists():
            p.unlink()
    return {"reset": True}

