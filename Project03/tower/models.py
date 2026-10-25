"""Contracts: the incident, the brief and every action request. Pydantic checks shape; triage.py and actions.py check meaning."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

Severity = Literal["P1", "P2", "P3", "P4"]
Status = Literal["WAITING_FOR_APPROVAL", "AUTO_RESOLVED", "NEEDS_PERSON", "CHANGE_DONE", "REJECTED"]


class Alert(BaseModel):
    alert_id: str
    time: str  # "YYYY-MM-DD HH:MM"
    source: str
    service: str
    check: str
    severity: Literal["critical", "major", "warning", "info"]
    status: Literal["firing", "resolved"]
    message: str


class AlertView(BaseModel):
    """An alert as the model and the screen see it: text hidden, flags attached."""
    alert_id: str
    time: str
    source: str
    service: str
    check: str
    severity: str
    status: str
    message: str  # redacted; or a withheld notice when the input check failed
    flagged: bool = False
    flag_reasons: list[str] = []
    original_shown: Optional[str] = None  # redacted original, shown to the engineer as inert quoted text, never to a model
    hidden: dict[str, int] = {}  # {"secrets": 2, "personal": 1}


class StepRef(BaseModel):
    runbook_id: str
    step_no: int
    action: str = ""

    @property
    def label(self) -> str:
        return f"{self.runbook_id} step {self.step_no}"


class ChangeRecommendation(StepRef):
    target_service: str


class IncidentBrief(BaseModel):
    summary: str = Field(min_length=10, max_length=600)  # two lines
    read_steps: list[StepRef] = []
    recommended_change: Optional[ChangeRecommendation] = None
    runbook_id: Optional[str] = None
    reason: str = ""
    similar_incident: Optional[str] = None
    status_update: Optional[str] = None  # draft for P1 and P2 (policy 8.1); a person sends it


class Approver(BaseModel):
    role: Literal["owner", "duty_manager"]
    team: str
    engineer: str
    why: str  # policy section, e.g. "owns the service (5.1)"


class Incident(BaseModel):
    incident_id: str
    opened: str
    last_alert: str
    alert_ids: list[str]
    services: list[str]
    root_cause: Optional[str] = None  # None when the service is not in the catalogue
    severity: Optional[Severity] = None
    status: Status
    runbook_id: Optional[str] = None
    recommended_step: Optional[int] = None
    action: str = "none"
    target: Optional[str] = None
    approvals_needed: int = 0
    approvers: list[Approver] = []
    freeze: bool = False
    similar_incident: Optional[str] = None
    flags: list[str] = []
    rules_applied: list[str] = []  # policy sections cited, with the reason
    alerts: list[AlertView] = []
    brief: Optional[IncidentBrief] = None
    reads: list[dict] = []  # [READ] steps already run: {step, tool, result, simulated}
    needs_person_reason: str = ""
    request_id: Optional[str] = None  # the open ActionRequest, if any
    crew: list[dict] = []  # the agent trace: who did what, with rules or a model


class ActionRequest(BaseModel):
    """One step on one service. A request that names two services does not validate (policy 5.4)."""
    incident_id: str
    runbook_id: str
    step_no: int
    action: str
    target_service: str
    reason: str = Field(min_length=3, max_length=500)

    @field_validator("target_service")
    @classmethod
    def one_service(cls, v: str) -> str:
        if any(ch in v for ch in ",;/ ") or not v:
            raise ValueError("an action request names exactly one service (policy 5.4)")
        return v


class ApprovalIn(BaseModel):
    approver: str
    decision: Literal["approve", "reject"] = "approve"
    reason: str = ""


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=5000)


class TriageIn(BaseModel):
    """Alerts in, incidents out. With no alerts given, the 22 starter alerts in the database are used."""
    alerts: list[Alert] = []
    use_starter: bool = False
    with_brief: bool = True
