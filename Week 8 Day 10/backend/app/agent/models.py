"""Shapes for Day 9: the operations agent. The same shapes are in the Day 9 section of frontend/src/api.ts."""

from typing import Literal

from pydantic import BaseModel


class ScreenError(Exception):
    """CaseFlow Classic's screen is not what the agent expected. str(e) says what is wrong (ENG-901)."""


class Decision(BaseModel):
    """What the gate says about one action (ENG-903)."""
    kind: Literal["allow", "ask", "deny"]
    reason: str


class AgentReply(BaseModel):
    """One turn of the model: what it thinks, and the one tool it calls next."""
    thought: str
    tool: str
    args: dict = {}


class Approval(BaseModel):
    """A person's decision on one action that writes to a system of record."""
    id: str
    run_id: str
    ticket_id: str
    person: str
    system: str
    tool: str
    target: str
    fingerprint: str           # what exactly will be written: the case, and every field on the confirm screen
    shows: list[list[str]] = []  # the confirm screen's rows, for the person to read
    reason: str = ""           # the agent's own words for why
    evidence: list[str] = []   # what the agent read before it asked
    shot: str | None = None
    status: Literal["pending", "approved", "rejected", "expired"] = "pending"
    decided_by: str = ""
    note: str = ""
    created_at: float = 0
    decided_at: float = 0
    workflow_id: str = ""      # Day 10: the case workflow waiting for this decision (empty for a Day 9 run)
    expires_at: float = 0      # Day 10: when the workflow stops waiting


class Step(BaseModel):
    n: int
    thought: str
    tool: str
    args: dict = {}
    target: str = ""
    decision: str = ""        # allow | approved | rejected | denied | expired
    observation: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    seconds: float = 0
    shot: str | None = None


class Run(BaseModel):
    id: str
    ticket_id: str
    person: str
    prompt: str = "ops_v1"
    model: str = ""
    mode: Literal["live", "shadow"] = "live"
    status: Literal["running", "waiting_approval", "recorded", "proposed", "handed_back", "stopped", "rejected", "error"] = "running"
    stop_reason: str = ""
    outcome: str = ""
    reason_code: str = ""
    reference: str = ""
    summary: str = ""
    started_at: float = 0
    ended_at: float = 0
    steps: list[Step] = []
    approvals: list[str] = []
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float | None = None
    queue_id: str = ""
    workflow_id: str = ""      # Day 10: the case workflow this run is a step of
