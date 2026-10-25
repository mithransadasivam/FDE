"""The service catalogue, on-call table (public columns only), runbooks and policy clauses, loaded once."""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from .settings import ROOT


@dataclass(frozen=True)
class Service:
    service_id: str
    name: str
    tier: int
    owner_team: str
    depends_on: tuple[str, ...]
    runbooks: tuple[str, ...]


@dataclass(frozen=True)
class Step:
    runbook_id: str
    no: int
    kind: str  # READ or CHANGE
    tool: str
    text: str

    @property
    def needs_prerequisite(self) -> bool:
        # RB-04 step 3: "Needs an approved capacity ticket first." The tower has no capacity tickets (policy 4.4).
        return bool(re.search(r"\bNeeds\b.*\bfirst\b", self.text))


@dataclass(frozen=True)
class Runbook:
    runbook_id: str
    title: str
    used_for: tuple[str, ...]
    steps: tuple[Step, ...]
    raw: str

    def step(self, no: int) -> Step | None:
        return next((s for s in self.steps if s.no == no), None)


@dataclass(frozen=True)
class Clause:
    clause_id: str  # "5.3"
    text: str


@dataclass
class Catalog:
    services: dict[str, Service]
    oncall: dict[str, dict]  # team -> {engineer, work_email}  (no personal_mobile, ever)
    runbooks: dict[str, Runbook]
    clauses: list[Clause]
    history: list[dict] = field(default_factory=list)

    DUTY = "Duty manager"

    def known(self, service_id: str) -> bool:
        return service_id in self.services

    def deps_closure(self, service_id: str) -> set[str]:
        """Everything this service depends on, directly or through others."""
        seen: set[str] = set()
        stack = list(self.services[service_id].depends_on) if service_id in self.services else []
        while stack:
            s = stack.pop()
            if s in seen or s not in self.services:
                continue
            seen.add(s)
            stack.extend(self.services[s].depends_on)
        return seen

    def dependants(self, service_id: str) -> list[str]:
        return sorted(s for s in self.services if service_id in self.deps_closure(s))

    def direct_dependants(self, service_id: str) -> list[str]:
        return sorted(s.service_id for s in self.services.values() if service_id in s.depends_on)

    def owner(self, service_id: str) -> dict:
        team = self.services[service_id].owner_team
        return {"team": team, **self.oncall.get(team, {"engineer": "unknown", "work_email": ""})}

    def duty_manager(self) -> dict:
        return {"team": self.DUTY, **self.oncall[self.DUTY]}

    def clause(self, cid: str) -> str:
        c = next((c for c in self.clauses if c.clause_id == cid), None)
        return c.text if c else ""

    def resolve_service(self, text: str) -> str | None:
        """Find a catalogue service named in free text (by id or by name)."""
        low = text.lower()
        for s in self.services.values():
            if s.service_id.lower() in low or s.name.lower() in low:
                return s.service_id
        return None

    def find_services(self, text: str) -> list[str]:
        low = text.lower()
        return [s.service_id for s in self.services.values() if s.service_id.lower() in low or s.name.lower() in low]


_STEP_RE = re.compile(r"^(\d+)\.\s+\[(READ|CHANGE)\]\s+`([a-z_]+)`:\s*(.*)$")


def parse_runbook(path: Path) -> Runbook:
    raw = path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    title = lines[0].lstrip("# ").strip()
    used = re.search(r"Used for:\s*(.+?)\.\s*$", raw, re.M)
    used_for = tuple(x.strip() for x in used.group(1).split(",")) if used else ()
    rid = path.stem
    steps = []
    for ln in lines:
        m = _STEP_RE.match(ln.strip())
        if m:
            steps.append(Step(rid, int(m.group(1)), m.group(2), m.group(3), m.group(4).strip()))
    return Runbook(rid, title, used_for, tuple(steps), raw)


def parse_policy(path: Path) -> list[Clause]:
    """Numbered clauses such as '5.3 Change freeze: ...', with continuation lines joined."""
    clauses: list[Clause] = []
    cur_id, cur = None, []
    for ln in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^(\d+\.\d+)\s+(.*)$", ln)
        if m:
            if cur_id:
                clauses.append(Clause(cur_id, " ".join(cur)))
            cur_id, cur = m.group(1), [m.group(2).strip()]
        elif cur_id and ln.startswith("    ") and ln.strip():
            cur.append(ln.strip())
        elif cur_id and (ln.startswith("#") or not ln.strip()):
            clauses.append(Clause(cur_id, " ".join(cur)))
            cur_id, cur = None, []
    if cur_id:
        clauses.append(Clause(cur_id, " ".join(cur)))
    return clauses


def load(con: sqlite3.Connection, root: Path = ROOT) -> Catalog:
    services = {}
    for r in con.execute("SELECT * FROM services"):
        services[r["service_id"]] = Service(
            r["service_id"], r["name"], r["tier"], r["owner_team"],
            tuple(x for x in r["depends_on"].split(";") if x), tuple(x for x in r["runbooks"].split(";") if x))
    oncall = {r["team"]: {"engineer": r["engineer"], "work_email": r["work_email"]}
              for r in con.execute("SELECT team, engineer, work_email FROM oncall")}  # never oncall_private
    runbooks = {p.stem: parse_runbook(p) for p in sorted((root / "docs" / "runbooks").glob("RB-*.md"))}
    clauses = parse_policy(root / "docs" / "OPERATIONS_POLICY.md")
    history = [dict(r) for r in con.execute("SELECT * FROM past_incidents")]
    return Catalog(services, oncall, runbooks, clauses, history)
