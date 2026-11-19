"""Day 8: what the Integrations screen shows (done, not a ticket)."""

import csv
import json
import time

import httpx

from app import store
from app.config import BANK_URL, MCP_RESOURCE, PERMISSIONS_FILE_8, WEBHOOK_SECRET
from app.integration import auth, notify
from app.integration.mcp_client import call_tool
from app.integration.models import TokenRejected, WebhookRejected
from app.integration.tokens import verify_access_token
from app.integration.webhooks import verify_webhook

PEOPLE = ["tom.reyes", "grace.mensah", "helen.achebe"]


def _get(path: str, **kw):
    try:
        r = httpx.get(f"{BANK_URL}{path}", timeout=10, **kw)
        return r.json() if r.status_code == 200 else None
    except httpx.HTTPError:
        return None


def _post(path: str, **kw):
    r = httpx.post(f"{BANK_URL}{path}", timeout=30, **kw)
    r.raise_for_status()
    return r.json()


def _not_built() -> dict:
    out = {"tokens": "", "webhooks": ""}
    try:
        verify_access_token("x", {"keys": []}, "", "", [])
    except NotImplementedError as e:
        out["tokens"] = str(e)
    except TokenRejected:
        pass
    try:
        verify_webhook({}, b"", "", 0, set())
    except NotImplementedError as e:
        out["webhooks"] = str(e)
    except WebhookRejected:
        pass
    return out


def status() -> dict:
    meta = _get("/.well-known/oauth-authorization-server")
    try:
        prm = httpx.get(MCP_RESOURCE.replace("/mcp", "/.well-known/oauth-protected-resource/mcp"), timeout=5).json()
    except httpx.HTTPError:
        prm = None
    return {"bank": {"up": meta is not None, "url": BANK_URL, "metadata": meta}, "mcp": {"up": prm is not None, "url": MCP_RESOURCE, "metadata": prm},
            "claude_command": f"claude mcp add --transport http kestrelmoor-kyc {MCP_RESOURCE}", "not_built": _not_built(),
            "people": PEOPLE}


# ---------------------------------------------------------------- Sign-in tab: token probes (ENG-801)
def token_probes() -> dict:
    nb = _not_built()["tokens"]
    data = _get("/course/token-probes")
    if data is None:
        return {"error": f"The bank's systems are not running at {BANK_URL}", "probes": [], "not_built": nb}
    jwks = _get("/jwks.json")
    out = []
    for p in data["probes"]:
        row = {k: p[k] for k in ("id", "what", "expect")}
        row["token_start"] = p["token"][:28] + "…"
        if nb:
            row.update(result=None, reason="", passed=None)
        else:
            try:
                ident = verify_access_token(p["token"], jwks, data["issuer"], data["audience"], ["kyc.read"])
                row.update(result="accept", reason=f"{ident.name} · {ident.role} · {' '.join(ident.scopes)}")
            except TokenRejected as e:
                row.update(result="refuse", reason=str(e))
            row["passed"] = row["result"] == p["expect"]
        out.append(row)
    done = [r for r in out if r["passed"] is not None]
    return {"not_built": nb, "audience": data["audience"], "issuer": data["issuer"], "probes": out,
            "summary": None if nb else {"passed": sum(r["passed"] for r in done), "total": len(out)},
            "checks": store.load("integration/mcp_token_checks.json", [])[-12:][::-1]}


# ---------------------------------------------------------------- Act as the person (ENG-802)
def act(person: str, tool: str, args: dict) -> dict:
    if person not in PEOPLE:
        raise KeyError(f"No course account {person}")
    token = auth.sign_in_as(person)
    started = time.time()
    res = call_tool(token, tool, args)
    audit = (_get("/audit", params={"limit": 6}) or {}).get("entries", [])
    return {"person": person, "tool": tool, "args": args, **res, "ms": round((time.time() - started) * 1000), "audit": audit}


def audit_log(system: str = "") -> dict:
    return _get("/audit", params={"system": system, "limit": 40}) or {"entries": []}


# ---------------------------------------------------------------- Webhooks and Slack (ENG-803)
def receive_webhook(headers: dict, body: bytes) -> dict:
    """The console's webhook endpoint. Raises WebhookRejected (logged) or NotImplementedError."""
    seen = set(store.load("integration/webhook_seen.json", []))
    log = store.load("integration/webhook_log.json", [])
    entry = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "signature": headers.get("x-kestrel-signature", "")[:30]}
    try:
        event = verify_webhook(headers, body, WEBHOOK_SECRET, time.time(), seen)
    except WebhookRejected as e:
        try:
            eid = json.loads(body).get("id")
        except ValueError:
            eid = None
        log.append({**entry, "event_id": eid, "outcome": "refused", "reason": str(e)})
        store.save("integration/webhook_log.json", log[-200:])
        raise
    store.save("integration/webhook_seen.json", sorted(seen)[-1000:])
    posted = notify.post(event["data"])
    log.append({**entry, "event_id": event["id"], "outcome": "accepted", "reason": "", "ticket": event["data"]["ticket_id"],
                "slack": [p["channel"] for p in posted]})
    store.save("integration/webhook_log.json", log[-200:])
    return {"received": event["id"], "slack": posted}


def webhooks() -> dict:
    return {"not_built": _not_built()["webhooks"], "log": store.load("integration/webhook_log.json", [])[::-1][:20],
            "deliveries": (_get("/kyc/webhook-deliveries") or {}).get("deliveries", [])[:20],
            "slack": (_get("/slack/channels") or {}).get("channels", [])}


def raise_exception(team_id: str) -> dict:
    return _post("/course/raise-exception", json={"team_id": team_id})


def webhook_probes() -> dict:
    return _post("/course/webhook-probes")


# ---------------------------------------------------------------- Permissions tab
def matrix() -> list[dict]:
    with open(PERMISSIONS_FILE_8, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    extra = store.load("integration/permission_rows.json", [])  # homework: rows for the document store
    return rows + extra


def _count(data) -> int | None:
    if isinstance(data, dict):
        for k in ("total",):
            if k in data:
                return data[k]
        for k in ("customers", "tickets", "documents"):
            if k in data:
                return len(data[k])
    return None


def _outcome(res: dict, expected: str) -> tuple[str, bool]:
    exp = expected.split()
    if not res["ok"]:
        return f"refused: {res['error']}", exp[0] == "refused"
    n = _count(res["data"])
    got = f"allowed {n}" if n is not None and len(exp) > 1 else "allowed"
    return got, got == expected


def permissions(run: bool = False) -> dict:
    rows = matrix()
    saved = store.load("integration/permission_run.json", None)
    if run:
        results = {}
        for r in rows:
            for p in PEOPLE:
                res = call_tool(auth.sign_in_as(p), r["tool"], json.loads(r["args"]))
                got, ok = _outcome(res, r[p])
                results[f"{r['id']}/{p}"] = {"got": got, "passed": ok}
        saved = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "results": results}
        store.save("integration/permission_run.json", saved)
    res = (saved or {}).get("results", {})
    cells = [res[f"{r['id']}/{p}"] for r in rows for p in PEOPLE if f"{r['id']}/{p}" in res]
    return {"people": PEOPLE, "rows": rows, "results": res, "at": (saved or {}).get("at"),
            "summary": {"passed": sum(c["passed"] for c in cells), "total": len(rows) * len(PEOPLE)} if cells else None}
