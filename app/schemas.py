"""Pydantic models: every piece of data is checked here (Prompt 2)."""
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class Role(str, Enum):
    HIRING_MANAGER = "hiring_manager"
    RECRUITER = "recruiter"


class Stage(str, Enum):
    APPLIED = "APPLIED"
    EXTRACTED = "EXTRACTED"
    REVIEW = "REVIEW"
    SCREENED = "SCREENED"
    SHORTLISTED = "SHORTLISTED"
    AI_INTERVIEW = "AI_INTERVIEW"
    HUMAN_INTERVIEW = "HUMAN_INTERVIEW"
    DECISION = "DECISION"
    WITHDRAWN = "WITHDRAWN"


# Day 1 uses APPLIED, EXTRACTED, REVIEW and WITHDRAWN (the others are listed so the board shows them).
# Day 2 adds SCREENED, SHORTLISTED and AI_INTERVIEW; Days 3-4 add HUMAN_INTERVIEW and DECISION.


class RubricItem(BaseModel):
    skill: str = Field(min_length=2, max_length=80)
    weight: int = Field(ge=1, le=40)
    must_have: bool = False
    evidence_from_note: str = Field(min_length=2, description="The hiring manager's own words")


class Rubric(BaseModel):
    items: list[RubricItem] = Field(min_length=5, max_length=12)
    min_years: float = Field(ge=0, le=20)

    @model_validator(mode="after")
    def weights_add_to_100(self):
        total = sum(i.weight for i in self.items)
        if total != 100:
            raise ValueError(f"rubric weights must add to 100, got {total}")
        names = [i.skill.strip().lower() for i in self.items]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            raise ValueError(f"duplicate skill in rubric: {', '.join(dupes)}")
        return self

    @property
    def total(self) -> int:
        return sum(i.weight for i in self.items)


class JobDescription(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    summary: str = Field(min_length=10)
    responsibilities: list[str] = Field(min_length=1)
    requirements: list[str] = Field(min_length=1)
    nice_to_have: list[str] = []

    def as_text(self) -> str:
        parts = [self.title, self.summary, *self.responsibilities, *self.requirements, *self.nice_to_have]
        return "\n".join(parts)


class JobDraft(BaseModel):
    job: JobDescription
    rubric: Rubric


class WordingFlag(BaseModel):
    phrase: str
    reason: str
    suggestion: str
    where: str = "voice note"


class StrField(BaseModel):
    value: str | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)


class NumField(BaseModel):
    value: float | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)


class ListField(BaseModel):
    value: list[str] | None = None
    confidence: float = Field(default=0.0, ge=0, le=1)


class CandidateProfile(BaseModel):
    """What the document agent reads from a CV: every field has a value and a confidence (0 to 1)."""
    name: StrField = StrField()
    email: StrField = StrField()
    phone: StrField = StrField()
    address: StrField = StrField()
    date_of_birth: StrField = StrField()
    current_title: StrField = StrField()
    jobs: ListField = ListField()
    years_experience: NumField = NumField()
    skills: ListField = ListField()
    certifications: ListField = ListField()
    education: StrField = StrField()


class BlindCandidate(BaseModel):
    """What scoring is allowed to see: skills and experience, never identity."""
    candidate_id: int
    current_title: str | None = None
    jobs: list[str] = []
    years_experience: float | None = None
    skills: list[str] = []
    certifications: list[str] = []
    education: str | None = None


from app.schemas_ext import *  # noqa: E402,F401,F403  (Day 2-4 handoff models)
