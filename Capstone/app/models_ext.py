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
    consent_recording: Mapped[bool] = mapped_column(Boolean, default=False)  # "I understand the interview is recorded" was ticked
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    person_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sample: Mapped[bool] = mapped_column(Boolean, default=False)  # a simulated candidate: shown as "SAMPLE: fictional candidate"
    review: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # the recruiter's OWN level for each must-have, saved before any audio is shown
    recording_built_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)  # full_conversation.mp3 and recording.json exist
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


class InterviewTurn(Base):
    """One question asked in an AI interview and the candidate's answer: the text, both audio files and the times. It mirrors the interview's
    saved state, so the recording, the replay and the scorecard can read plain rows."""
    __tablename__ = "interview_turns"
    id: Mapped[int] = mapped_column(primary_key=True)
    interview_id: Mapped[int] = mapped_column(ForeignKey("interview_sessions.id"))
    n: Mapped[int] = mapped_column(default=1)
    question: Mapped[str] = mapped_column(Text, default="")
    why: Mapped[str] = mapped_column(Text, default="")
    skill: Mapped[str | None] = mapped_column(String(100), nullable=True)
    kind: Mapped[str] = mapped_column(String(20), default="technical")  # opening, technical, behavioural or follow_up
    guard: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # the question guard's results (Day 2, prompt 9)
    question_audio: Mapped[str | None] = mapped_column(String(300), nullable=True)
    answer_audio: Mapped[str | None] = mapped_column(String(300), nullable=True)
    transcript: Mapped[str] = mapped_column(Text, default="")
    diagram: Mapped[str | None] = mapped_column(Text, nullable=True)  # Mermaid text of a diagram drawn for this question
    diagram_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # title, description, expected points, weakness: never shown to the candidate
    shown_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    answer_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    answer_ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    score: Mapped[int | None] = mapped_column(nullable=True)
    quote: Mapped[str] = mapped_column(Text, default="")
    hint: Mapped[str] = mapped_column(Text, default="")
    skipped: Mapped[bool] = mapped_column(Boolean, default=False)


class AppSetting(Base):
    """Company settings (name, colour, contact): one row per key. Only the hiring manager can change them, and each change is logged."""
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


# ---- integrations and candidates' data rights ---------------------------------------------------------------------------------------------------
class ApiKey(Base):
    """A key for the read-only REST API. Only a hash is kept: the key itself is shown once, when it is made."""
    __tablename__ = "api_keys"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    prefix: Mapped[str] = mapped_column(String(16))
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class Webhook(Base):
    __tablename__ = "webhooks"
    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(500))
    events: Mapped[list] = mapped_column(JSON)
    secret: Mapped[str] = mapped_column(String(80))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class WebhookDelivery(Base):
    """Every event a webhook was due, and what happened. Nothing leaves the machine unless webhooks_live is on."""
    __tablename__ = "webhook_deliveries"
    id: Mapped[int] = mapped_column(primary_key=True)
    webhook_id: Mapped[int] = mapped_column(ForeignKey("webhooks.id"))
    event: Mapped[str] = mapped_column(String(60))
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(40), default="queued")  # queued, sent, failed or not_sent
    http_status: Mapped[int | None] = mapped_column(nullable=True)
    error: Mapped[str] = mapped_column(Text, default="")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class DataRequest(Base):
    """A candidate asks for a copy of their data or for it to be deleted. A PERSON decides a deletion (rule 1): nothing is erased automatically."""
    __tablename__ = "data_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"))
    kind: Mapped[str] = mapped_column(String(20))  # export or delete
    status: Mapped[str] = mapped_column(String(20), default="REQUESTED")  # REQUESTED, DONE or REFUSED
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    decided_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")
