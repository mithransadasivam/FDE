"""Typed handoffs for Days 2-4 (Pydantic for every handoff between agents). Re-exported from app/schemas.py."""
from pydantic import BaseModel, Field, field_validator


class ItemScore(BaseModel):
    """One rubric skill scored 0-3 with the exact CV sentence behind it (rule 2)."""
    skill: str
    weight: int = Field(ge=0, le=100)
    score: int = Field(ge=0, le=3)
    quote: str = ""
    verified: bool = False  # set by code, never by the model

    @field_validator("quote")
    @classmethod
    def strip(cls, v: str) -> str:
        return (v or "").strip()


class ScreeningResult(BaseModel):
    candidate_id: int
    items: list[ItemScore]

    @property
    def weighted_total(self) -> float:
        """0-100: the weights add to 100 and each score is out of 3."""
        return round(sum(i.weight * i.score for i in self.items) / 3, 1)


class PlanItem(BaseModel):
    question_id: str
    skill: str
    core: bool
    diagram: str | None = None
    reason: str = ""


class InterviewPlan(BaseModel):
    candidate_id: int
    items: list[PlanItem] = Field(min_length=1, max_length=8)


class AnswerScore(BaseModel):
    question_id: str
    skill: str = ""
    score: int = Field(ge=0, le=3)
    max_score: int = Field(default=3, ge=0, le=3)  # a hint lowers the best score an answer can earn
    quote: str = ""
    verified: bool = False
    key_points_hit: list[str] = []
    key_points_missed: list[str] = []
    hint_used: bool = False
    follow_up_asked: str | None = None
    skipped: bool = False
    excluded_reason: str | None = None  # for example: the answer mentioned a protected trait, which is never scored
    audio_file: str | None = None
    audio_start_s: float = 0.0


class Scorecard(BaseModel):
    candidate_id: int
    answers: list[AnswerScore]
    ended_reason: str = ""
    second_scorer: dict[str, int] = {}  # question_id -> the checker model's score
    disagreements: list[str] = []  # question ids where the two scorers differ by 1 or more: sent to the recruiter

    @property
    def total(self) -> float:
        scored = [a for a in self.answers if not a.skipped and a.excluded_reason is None]
        return round(sum(a.score for a in scored) / len(scored), 2) if scored else 0.0


class Decision(BaseModel):
    candidate_id: int
    decision: str  # ADVANCE, HOLD, NOT_THIS_TIME or OFFER_RECOMMENDED
    reason: str = Field(min_length=3)
    actor: str


class CopilotEvent(BaseModel):
    """One thing the copilot panel shows, with the replay time (seconds) it happened."""
    t: float
    kind: str  # transcript, key_point, suggestion, cv_check, warning, coverage
    data: dict


class DraftEmail(BaseModel):
    candidate_id: int
    kind: str
    subject: str
    body: str
    slot: str | None = None


class Finding(BaseModel):
    check: str
    severity: str = "high"
    detail: str
    candidate_id: int | None = None
