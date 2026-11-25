"""Ticket ENG-803: accept a webhook only if the ticketing system really sent it, just now, for the first time.

The bank's ticketing system calls POST /api/hooks/kyc-exceptions when a KYC exception is created. The address is not secret:
anyone who can reach it can post to it. Each genuine delivery carries a header

    X-Kestrel-Signature: t=1762851600,v1=5f8c…

where v1 is the hex HMAC-SHA256, keyed with the shared secret, of the bytes  f"{t}." + body.
"""

import hashlib
import hmac
import json
import re

from app.integration.models import WebhookRejected

HEADER = "x-kestrel-signature"
TOLERANCE_S = 300


def verify_webhook(headers: dict, body: bytes, secret: str, now: float, seen: set[str]) -> dict:
    """Return the event (the JSON body as a dict), or raise WebhookRejected with the first reason that applies, word for word:

      1. No X-Kestrel-Signature header (header names are case-insensitive):    "Missing signature"
      2. The header is not "t=<integer>,v1=<hex>":                               "Malformed signature"
      3. v1 does not match the HMAC of f"{t}." + body (compare with hmac.compare_digest):
                                                                                 "Bad signature"
      4. t is more than TOLERANCE_S seconds from `now`, either way:              "Too old: sent 600 s ago"
      5. The event's "id" is already in `seen`:                                  "Already received: evt_…"
    Otherwise add the event's id to `seen` and return the event.
    """
    lowered = {k.lower(): v for k, v in headers.items()}
    header = lowered.get(HEADER)
    if not header:
        raise WebhookRejected("Missing signature")
    parts = dict(p.split("=", 1) for p in header.split(",") if "=" in p)
    t_text, v1 = parts.get("t", ""), parts.get("v1", "")
    if not re.fullmatch(r"-?\d+", t_text) or not v1:
        raise WebhookRejected("Malformed signature")
    t = int(t_text)
    expected = hmac.new(secret.encode(), f"{t}.".encode() + body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, v1):
        raise WebhookRejected("Bad signature")
    if abs(now - t) > TOLERANCE_S:
        raise WebhookRejected(f"Too old: sent {int(now - t)} s ago")
    event = json.loads(body)
    if event.get("id") in seen:
        raise WebhookRejected(f"Already received: {event.get('id')}")
    seen.add(event.get("id"))
    return event
