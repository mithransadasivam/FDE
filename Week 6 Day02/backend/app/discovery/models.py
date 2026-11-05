"""Day 1 data models: everything discovery produces is one of these."""

from typing import Literal, Optional

from pydantic import BaseModel, Field

Area = Literal["goals", "process", "data", "risk", "success"]


class QuestionIn(BaseModel):
    area: Area
    text: str = Field(min_length=10, max_length=220)
    why: str = Field(min_length=5, max_length=220, description="What the answer will tell us")


class QuestionPlan(BaseModel):
    questions: list[QuestionIn] = Field(min_length=10, max_length=25)


class Question(QuestionIn):
    id: str
    starred: bool = False


FindingKind = Literal["pain_point", "requirement", "constraint", "open_question"]


class FindingIn(BaseModel):
    kind: FindingKind
    title: str = Field(min_length=3, max_length=90)
    detail: str = Field(min_length=5, max_length=400)
    speaker: str = Field(min_length=2, description="Who said it, as named in the transcript")
    quote: str = Field(min_length=10, description="Exact words from the transcript")
    frequency: Optional[int] = Field(default=None, ge=1, le=5, description="Pain points: how often, 1-5")
    impact: Optional[int] = Field(default=None, ge=1, le=5, description="Pain points: how much it hurts, 1-5")


class ExtractedFindings(BaseModel):
    findings: list[FindingIn] = Field(min_length=1, max_length=30)


class Finding(FindingIn):
    id: str
    evidence_ok: Optional[bool] = None  # set by verify_evidence()
    review: Literal["unreviewed", "confirmed", "wrong"] = "unreviewed"


class Criterion(BaseModel):
    id: str
    name: str
    kind: Literal["business", "quality", "guardrail"]
    metric: str = ""
    baseline: Optional[float] = None
    target: Optional[float] = None
    unit: str = ""
    direction: Literal["increase", "decrease"] = "increase"
    measured_how: str = ""
    owner: str = ""
    by_when: str = ""


class UseCase(BaseModel):
    id: str
    name: str
    description: str
    value: int = Field(ge=1, le=5)
    feasibility: int = Field(ge=1, le=5)
    risk: int = Field(ge=1, le=5)
    excluded_reason: str = ""
    first_choice: bool = False
