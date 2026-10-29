"""API keys, rate limiting and webhooks (product features).

The REST API is READ-ONLY and BLIND: it returns candidate numbers, stages, scores and quotes, never a name or contact detail (rules 3 and 9). A key is shown once
and only its hash is kept. Webhooks announce events (an interview finished, a shortlist was approved, a decision was recorded, someone asked for a person) with
a signature, but nothing leaves the machine unless WEBHOOKS_LIVE is on: otherwise each delivery is recorded as "not sent", so the feature can be tried safely.
"""
import hashlib
import hmac
import json
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models_ext import ApiKey, Webhook, WebhookDelivery

EVENTS = {"interview.finished": "An AI interview finished", "shortlist.approved": "A shortlist was approved by a recruiter",
          "decision.recorded": "A final decision was recorded", "person.requested": "A candidate asked for a person instead", "test": "A test event"}
RATE_LIMIT = 60  # requests per minute per key
_hits: dict[int, deque] = defaultdict(deque)


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def create_key(db: Session, name: str, actor: str) -> tuple[ApiKey, str]:
    """Makes a key. Returns the row and the key itself, which is shown once and never stored."""
    key = "hi_live_" + secrets.token_urlsafe(24)
    row = ApiKey(name=name.strip()[:100] or "API key", prefix=key[:12], key_hash=_hash(key), created_by=actor)
    db.add(row)
    db.flush()
    return row, key


def find_key(db: Session, presented: str | None) -> ApiKey | None:
    if not presented:
        return None
    row = db.scalar(select(ApiKey).where(ApiKey.key_hash == _hash(presented.strip())))
    return row if row and not row.revoked else None


def over_limit(key_id: int, now: float | None = None) -> bool:
    """True when this key has already made RATE_LIMIT requests in the last minute (a sliding window kept in memory)."""
    now = now if now is not None else time.monotonic()
    q = _hits[key_id]
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        return True
    q.append(now)
    return False


def reset_limits() -> None:
    _hits.clear()


# ---- webhooks ------------------------------------------------------------------------------------------------------------------------------------------
def sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _deliver(db: Session, hook: Webhook, delivery: WebhookDelivery) -> None:
    body = json.dumps(delivery.payload, sort_keys=True).encode()
    if not get_settings().webhooks_live:
        delivery.status, delivery.error = "not_sent", "WEBHOOKS_LIVE is off: recorded only, nothing was sent"
        return
    import httpx

    try:
        r = httpx.post(hook.url, content=body, timeout=5, headers={"Content-Type": "application/json", "X-Signature": sign(hook.secret, body), "X-Event": delivery.event})
        delivery.http_status, delivery.status = r.status_code, "sent" if r.is_success else "failed"
    except Exception as e:  # a slow or broken receiver must never hold up hiring
        delivery.status, delivery.error = "failed", f"{type(e).__name__}: {str(e)[:150]}"


def emit(db: Session, event: str, payload: dict) -> int:
    """Records (and, if live, sends) the event to every active webhook that listens for it. Never raises: it must not break the action that caused it."""
    try:
        n = 0
        for hook in db.scalars(select(Webhook).where(Webhook.active.is_(True))):
            if event in (hook.events or []):
                d = WebhookDelivery(webhook_id=hook.id, event=event, payload={"event": event, "at": datetime.now(timezone.utc).isoformat(), **payload})
                db.add(d)
                db.flush()
                _deliver(db, hook, d)
                n += 1
        return n
    except Exception:
        return 0
