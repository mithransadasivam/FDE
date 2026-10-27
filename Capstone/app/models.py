"""SQLAlchemy tables (Prompt 2). Pydantic models for the same data are in app/schemas.py."""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(30))
    password_hash: Mapped[str] = mapped_column(String(200))


class Requisition(Base):
    __tablename__ = "requisitions"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    audio_path: Mapped[str] = mapped_column(String(500), default="")
    audio_name: Mapped[str] = mapped_column(String(300), default="")
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    job: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rubric: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    wording_flags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # DRAFT / TRANSCRIBED / GENERATED / APPROVED / PUBLISHED, or ERROR if reading the note failed
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    candidates: Mapped[list["Candidate"]] = relationship(back_populates="requisition")


class Candidate(Base):
    __tablename__ = "candidates"
    id: Mapped[int] = mapped_column(primary_key=True)
    requisition_id: Mapped[int] = mapped_column(ForeignKey("requisitions.id"))
    requisition: Mapped[Requisition] = relationship(back_populates="candidates")
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    cv_path: Mapped[str] = mapped_column(String(500))
    cv_name: Mapped[str] = mapped_column(String(300))
    cv_format: Mapped[str] = mapped_column(String(20))  # pdf / docx / scan / screenshot
    consent_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    access_token: Mapped[str] = mapped_column(String(100), unique=True)
    profile: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    stage: Mapped[str] = mapped_column(String(20), default="APPLIED")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ReviewItem(Base):
    __tablename__ = "review_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"))
    field: Mapped[str] = mapped_column(String(50))
    value: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)


class DecisionLog(Base):
    __tablename__ = "decision_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    actor: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)


from app import models_ext  # noqa: E402,F401  (registers the Day 2-4 tables)
