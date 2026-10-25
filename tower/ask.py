"""Operator questions. The order at every door (Day 15 to 17, in one place):

  input check -> private-contact check -> route (data / small / large) -> cache -> retrieve -> model -> tools -> output check

* data  : status and facts are answered straight from the database with no model call (policy numbers, owners, dependants, counts).
* small : simple runbook and policy look-ups go to SMALL_MODEL.
* large : everything that needs judgement, a summary or a draft goes to LLM_MODEL.

Which questions are safe without a model? Those whose answer is a row or a count in our own tables: nothing to interpret, so a model could
only add mistakes. Not safe: anything that summarises, explains why, compares, or drafts.
"""
from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from typing import Iterator

from . import guardrails, prompts
from .catalog import Catalog
from .models import Incident
from .settings import PROMPT_VERSION

_LARGE_HINTS = re.compile(r"\b(summari[sz]e|draft|why|compare|explain|both|before|saturday|sunday|weekend|friday|looked like|"
                          r"have we seen|same time|duty manager)\b", re.I)
_SMALL_HINTS = re.compile(r"\bRB-?\d{2}\b|runbook|\[change\]|\bwhat makes\b|difference between|what happens when|can the system|"
                          r"what should i do about|\bpolicy\b|\bhow do i\b|which steps", re.I)


@dataclass
class AskResult:
    answer: str
    sources: list[str] = field(default_factory=list)
    route: str = "large"  # data | small | large | cache | blocked
    model: str = ""
    cached: bool = False
    blocked: bool = False
    reasons: list[str] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    ms: float = 0.0
    ttft_ms: float | None = None
    tools: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def classify(question: str, routing: bool = True) -> str:
    """The routing rule, in code. With routing off (the baseline) every question goes to the large model."""
    if not routing:
        return "large"
    if _data_pattern(question) is not None:
        return "data"
    if _SMALL_HINTS.search(question) and not _LARGE_HINTS.search(question):
        return "small"
    return "large"


# ---- data answers ---------------------------------------------------------------------------------------------------

_DATA_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("change_steps", re.compile(r"which steps in (RB-?\d{2}) need approval|list the \[change\] steps in (RB-?\d{2})|\[change\] steps (?:in|of) (RB-?\d{2})", re.I)),
    ("open", re.compile(r"\b(which|what|list|show)\b.*\bincidents\b.*\bopen\b|\bopen incidents\b", re.I)),
    ("longest_p1", re.compile(r"longest .*p1|p1 .*took .*longest", re.I)),
    ("freeze", re.compile(r"change freeze.*(start|end|begin)|when does the (change )?freeze", re.I)),
    ("tier_list", re.compile(r"which services are tier[- ]?(\d)", re.I)),
    ("is_tier", re.compile(r"\bis (.+?) tier[- ]?(\d)\b", re.I)),
    ("owner", re.compile(r"\bwho owns (?:the )?(.+?)\??$", re.I)),
    ("depends", re.compile(r"services depend on (?:the )?(.+?)\??$", re.I)),
    ("oncall", re.compile(r"(?:which team|who) is on[- ]call for (?:the )?(.+?)\??$", re.I)),
    ("alert_count", re.compile(r"how many alerts fired for (?:the )?(.+?)(?: today)?\??$", re.I)),
    ("threshold", re.compile(r"threshold .* on (?:the )?(.+?)\??$", re.I)),
    ("status", re.compile(r"\bstatus of (?:the )?(.+?)\??$|\bis (?:the )?(.+?) healthy\??$", re.I)),
]


def _data_pattern(question: str):
    q = question.strip()
    for name, rx in _DATA_PATTERNS:
        m = rx.search(q)
        if m:
            return name, m
    return None


def _live_state(con) -> list[Incident]:
    return [Incident.model_validate_json(r["data"]) for r in con.execute("SELECT data FROM incidents ORDER BY incident_id")]


def _service_in(cat: Catalog, text: str | None) -> str | None:
    return cat.resolve_service(text or "") if text else None


def data_answer(question: str, cat: Catalog, con, now: str) -> tuple[str, list[str]] | None:
    hit = _data_pattern(question)
    if hit is None:
        return None
    name, m = hit
    g = [x for x in m.groups() if x]
    if name == "change_steps":  # a filter over parsed runbook steps: exact, so no model (the 8B model once answered "steps 2 and 3")
        rid = re.sub(r"(?i)^rb-?", "RB-", g[0])
        rb = cat.runbooks.get(rid)
        if rb is None:
            return None
        ch = [s for s in rb.steps if s.kind == "CHANGE"]
        body = "; ".join(f"step {s.no} [{s.kind}] {s.tool}: {s.text}" for s in ch)
        return (f"{rid} ({rb.title}) has {len(ch)} [CHANGE] step(s), and each needs approval (policy 5): {body}" if ch
                else f"{rid} has no [CHANGE] steps."), [f"{rid} step {s.no}" for s in ch] or [rid]
    if name == "open":
        incs = [i for i in _live_state(con) if i.status in ("WAITING_FOR_APPROVAL", "NEEDS_PERSON")]
        if not incs:
            return "No incidents are open right now (nothing waiting for approval or for a person).", ["incidents"]
        lines = [f"{i.incident_id} {i.severity or '--'} {i.root_cause or 'unknown service'} ({i.status.replace('_', ' ').lower()})" for i in incs]
        return f"{len(incs)} incident(s) are open: " + "; ".join(lines) + ".", [i.incident_id for i in incs]
    if name == "longest_p1":
        row = con.execute("SELECT incident_id, minutes_to_resolve, service FROM past_incidents WHERE severity='P1' "
                          "ORDER BY minutes_to_resolve DESC LIMIT 1").fetchone()
        return (f"The longest past P1 was {row['incident_id']} on {row['service']}: {row['minutes_to_resolve']} minutes.",
                [row["incident_id"]]) if row else None
    if name == "freeze":
        return cat.clause("5.3"), ["policy 5.3"]
    if name == "tier_list":
        tier = int(g[0])
        svcs = [s.service_id for s in cat.services.values() if s.tier == tier]
        return f"Tier {tier} services: {', '.join(svcs)}.", [f"services {s}" for s in svcs]
    if name == "oncall" and g:  # "Which team is on call for Identity?" names a team, not a service
        team = next((t for t in cat.oncall if t.lower() == g[0].strip().lower()), None)
        if team:
            p = cat.oncall[team]
            return f"{team} on-call: {p['engineer']} ({p['work_email']}). Contact the team with page_oncall.", [f"oncall {team}"]
    svc = _service_in(cat, g[0] if g else None)
    if svc is None:
        return None
    sv = cat.services[svc]
    if name == "is_tier":
        want = int(g[1])
        return f"{'Yes' if sv.tier == want else 'No'}: {svc} is tier {sv.tier}.", [f"services {svc}"]
    if name == "owner":
        o = cat.owner(svc)
        return f"{svc} ({sv.name}) is owned by {o['team']}; the on-call engineer is {o['engineer']} ({o['work_email']}).", [f"services {svc}", f"oncall {o['team']}"]
    if name == "depends":
        d = cat.dependants(svc)
        return (f"Services that depend on {svc}, directly or through others: {', '.join(d)}." if d else f"Nothing depends on {svc}."), [f"services {svc}"]
    if name == "oncall":
        o = cat.owner(svc)
        return f"{o['team']} owns {svc}; on call: {o['engineer']} ({o['work_email']}). Contact them with page_oncall.", [f"oncall {o['team']}"]
    if name == "alert_count":
        day = now[:10]
        n = con.execute("SELECT COUNT(*) c FROM alerts WHERE service=? AND substr(time,1,10)=?", (svc, day)).fetchone()["c"]
        return f"{n} alert(s) fired for {svc} on {day}.", [f"services {svc}"]
    if name == "threshold":
        rows = con.execute("SELECT alert_id, message FROM alerts WHERE service=? AND message LIKE '%threshold%' ORDER BY time DESC", (svc,)).fetchall()
        if not rows:
            return f"No alert for {svc} states a threshold.", [f"services {svc}"]
        th = re.search(r"\(threshold ([^)]+)\)", rows[0]["message"])
        return f"The alert threshold for {svc} is {th.group(1) if th else 'in the alert text'}.", [f"alert {rows[0]['alert_id']}"]
    if name == "status":
        incs = [i for i in _live_state(con) if svc in i.services]
        if not incs:
            return (f"{svc} ({sv.name}): no incident involves it right now. "
                    f"Tier {sv.tier}, owned by {sv.owner_team}."), [f"services {svc}"]
        i = incs[-1]
        cause = "" if i.root_cause == svc else f" Root cause: {i.root_cause}."
        return (f"{svc} ({sv.name}) is in {i.incident_id}: {i.severity or '--'}, {i.status.replace('_', ' ').lower()}.{cause} "
                f"{i.approvals_needed} approval(s) needed."), [i.incident_id, f"services {svc}"]
    return None


# ---- cache ---------------------------------------------------------------------------------------------------------

class AnswerCache:
    """Keyed on the question and everything that could change the answer: the prompt version, the model, and the latest alert
    time for the services in the question (or for all alerts when none is named). A new alert changes the key, so it misses."""

    def __init__(self, ttl_s: float):
        self.ttl = ttl_s
        self.items: dict[str, tuple[float, AskResult]] = {}

    @staticmethod
    def key(question: str, model: str, latest_alert: str) -> str:
        norm = re.sub(r"\s+", " ", question.strip().lower())
        return hashlib.sha256(f"{norm}|{PROMPT_VERSION}|{model}|{latest_alert}".encode()).hexdigest()

    def get(self, k: str) -> AskResult | None:
        hit = self.items.get(k)
        if hit and time.time() - hit[0] <= self.ttl:
            return hit[1]
        self.items.pop(k, None)
        return None

    def put(self, k: str, r: AskResult) -> None:
        if len(self.items) > 500:
            self.items.pop(next(iter(self.items)))
        self.items[k] = (time.time(), r)

    def clear(self) -> None:
        self.items.clear()


# ---- sentence-level release for streaming ----------------------------------------------------------------------------

def sentence_release(buffer: str) -> int:
    """How many characters of `buffer` end at a sentence boundary and can be checked and shown."""
    cut = 0
    for m in re.finditer(r"[.!?\n](?=\s|$)", buffer):
        cut = m.end()
    return cut
