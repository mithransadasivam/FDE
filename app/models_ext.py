"""Tables added for Days 2-4. They are new tables only, so the Day 1 tables are untouched. Imported by app/models.py."""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, OpsBase


def now() -> datetime:
    return datetime.now(timezone.utc)


class CvText(Base):
    """The raw text read from a CV. Kept apart from the profile: only the document agent and the red-team script read it."""
    __tablename__ = "cv_texts"
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), primary_key=True)
    text: Mapped[str] = mapped_column(Text, default="")
    pdf_metadata: Mapped[str] = mapped_column(Text, default="")


class Flag(Base):
    """Something the guardrails noticed, for a person to see (for example: instructions in a CV were ignored)."""
    __tablename__ = "flags"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    candidate_id: Mapped[int | None] = mapped_column(ForeignKey("candidates.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(60))
    detail: Mapped[str] = mapped_column(Text, default="")


class ItemScoreRow(Base):
    __tablename__ = "item_scores"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"))
    requisition_id: Mapped[int] = mapped_column(ForeignKey("requisitions.id"))
    skill: Mapped[str] = mapped_column(String(100))
    weight: Mapped[int] = mapped_column(default=0)
    score: Mapped[int] = mapped_column(default=0)
    quote: Mapped[str] = mapped_column(Text, default="")
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20), default="ok")  # ok, or returned (sent back by the compliance reviewer)
    overridden_by: Mapped[str | None] = mapped_column(String(200), nullable=True)


class ShortlistEntry(Base):
    __tablename__ = "shortlist"
    id: Mapped[int] = mapped_column(primary_key=True)
    requisition_id: Mapped[int] = mapped_column(ForeignKey("requisitions.id"))
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"))
    rank: Mapped[int] = mapped_column(default=0)
    weighted_total: Mapped[float] = mapped_column(Float, default=0.0)
    strengths: Mapped[list | None] = mapped_column(JSON, nullable=True)
    gaps: Mapped[list | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="SUGGESTED")  # SUGGESTED, APPROVED or NOT_SELECTED


class InterviewSession(Base):
    """One AI first-round interview. The state is saved after every turn so a dropped connection resumes."""
    __tablename__ = "interview_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="NOT_STARTED")  # NOT_STARTED, IN_PROGRESS, DONE, PERSON_REQUESTED
    notice_ack: Mapped[bool] = mapped_column(Boolean, default=False)
    plan: Mapped[list | None] = mapped_column(JSON, nullable=True)
    state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scorecard: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)


class HumanInterview(Base):
    """A recruiter-led interview followed by the copilot (a recorded interview is replayed as if it were live)."""
    __tablename__ = "human_interviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"))
    recording: Mapped[str] = mapped_column(String(300), default="")
    notice_ack: Mapped[bool] = mapped_column(Boolean, default=False)
    events: Mapped[list | None] = mapped_column(JSON, nullable=True)
    draft_scorecard: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    recruiter_scores: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="CREATED")


class EmailDraft(Base):
    __tablename__ = "email_drafts"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"))
    kind: Mapped[str] = mapped_column(String(30))  # invitation, update, decision or explanation
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    slot: Mapped[str | None] = mapped_column(String(60), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")  # DRAFT, SENT or REJECTED
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    decided_by: Mapped[str | None] = mapped_column(String(200), nullable=True)


class OutboxLog(Base):
    """Sent means a row here. No real mail server exists."""
    __tablename__ = "outbox"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    draft_id: Mapped[int] = mapped_column(ForeignKey("email_drafts.id"))
    to_candidate: Mapped[int] = mapped_column(ForeignKey("candidates.id"))
    approved_by: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(300))


class FinalDecision(Base):
    __tablename__ = "final_decisions"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"))
    decision: Mapped[str] = mapped_column(String(30))  # ADVANCE, HOLD, NOT_THIS_TIME or OFFER_RECOMMENDED
    reason: Mapped[str] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(String(200))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ComplianceFinding(Base):
    __tablename__ = "compliance_findings"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    candidate_id: Mapped[int | None] = mapped_column(ForeignKey("candidates.id"), nullable=True)
    check: Mapped[str] = mapped_column(String(60))
    severity: Mapped[str] = mapped_column(String(20), default="high")
    detail: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="OPEN")  # OPEN or RESOLVED


class ExplanationRequest(Base):
    __tablename__ = "explanation_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    draft_id: Mapped[int | None] = mapped_column(ForeignKey("email_drafts.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="REQUESTED")


class ModelCall(OpsBase):
    """Every model call with the prompt that was sent: the prompt log the compliance reviewer scans, and the cost ledger."""
    __tablename__ = "model_calls"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    agent: Mapped[str] = mapped_column(String(40), default="")
    task: Mapped[str] = mapped_column(String(30), default="")
    tier: Mapped[str] = mapped_column(String(20), default="")
    model: Mapped[str] = mapped_column(String(120), default="")
    candidate_id: Mapped[int | None] = mapped_column(nullable=True)
    prompt_system: Mapped[str] = mapped_column(Text, default="")
    prompt_user: Mapped[str] = mapped_column(Text, default="")
    tokens_in: Mapped[int] = mapped_column(default=0)
    tokens_out: Mapped[int] = mapped_column(default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    simulated: Mapped[bool] = mapped_column(Boolean, default=True)  # True in fake mode: the cost the call WOULD have had
    cached: Mapped[bool] = mapped_column(Boolean, default=False)
    sees_identity: Mapped[bool] = mapped_column(Boolean, default=False)


class AgentTrace(OpsBase):
    __tablename__ = "agent_traces"
    id: Mapped[int] = mapped_column(primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(40), default="")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    agent: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(100))
    candidate_id: Mapped[int | None] = mapped_column(nullable=True)
    duration_ms: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(20), default="ok")
    attrs: Mapped[dict | None] = mapped_column(JSON, nullable=True)
