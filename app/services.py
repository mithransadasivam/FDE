"""Background work: transcription now; CV reading is added in Prompt 11."""
from pathlib import Path

from sqlalchemy import select

from app.agents.document import extract_profile
from app.agents.wording import check_wording
from app.ai.voice import transcribe
from app.config import get_settings
from app.db import SessionLocal
from app.models import Candidate, DecisionLog, Requisition, ReviewItem
from app.schemas import CandidateProfile, Stage
from app.supervisor import move


def transcribe_requisition(req_id: int) -> None:
    """Runs after the upload page has already replied (FastAPI background task)."""
    db = SessionLocal()
    try:
        req = db.get(Requisition, req_id)
        if req is None:
            return
        try:
            req.transcript = transcribe(Path(req.audio_path), req.audio_name)
            req.status = "TRANSCRIBED"
            req.wording_flags = [f.model_dump() for f in check_wording(req.transcript, "voice note")]
            req.error = None
            db.add(DecisionLog(actor="system", action="transcribed", subject=f"requisition:{req.id}",
                               reason=f"{len(req.transcript.split())} words"))
        except Exception as e:  # shown on the page, never swallowed
            req.status = "ERROR"
            req.error = f"Transcription failed: {e}"
            db.add(DecisionLog(actor="system", action="transcription failed", subject=f"requisition:{req.id}", reason=str(e)))
        db.commit()
    finally:
        db.close()


CORE_FIELDS = ["name", "email", "phone", "current_title", "jobs", "years_experience", "skills", "certifications", "education"]
OPTIONAL_FIELDS = ["address", "date_of_birth"]  # only worth a person's time when the reader saw something but was unsure


def value_text(value) -> str:
    """How a field value is shown and edited: lists are separated by semicolons."""
    if value is None:
        return ""
    if isinstance(value, list):
        return "; ".join(str(v) for v in value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value)) if value >= 10 else str(value)
    return str(value)


def fields_to_review(profile: CandidateProfile, threshold: float, failed: bool = False) -> list[tuple[str, str, float]]:
    """(field, value, confidence) for every field below the threshold."""
    out = []
    for name in CORE_FIELDS + OPTIONAL_FIELDS:
        f = getattr(profile, name)
        if failed or (name in CORE_FIELDS and f.confidence < threshold) or (name in OPTIONAL_FIELDS and 0 < f.confidence < threshold):
            if failed and name in OPTIONAL_FIELDS:
                continue
            out.append((name, value_text(f.value), f.confidence))
    return out


def process_candidate(cand_id: int) -> None:
    """Reads the CV in a background task after the apply page has replied (Prompt 11)."""
    db = SessionLocal()
    try:
        cand = db.get(Candidate, cand_id)
        if cand is None:
            return
        failed = False
        try:
            profile = extract_profile(Path(cand.cv_path), cand.cv_format)
            cand.error = None
        except Exception as e:  # never silently drop a CV: it goes to REVIEW with the error
            profile, failed = CandidateProfile(), True
            cand.error = f"The CV could not be read: {e}"
        cand.profile = profile.model_dump()
        for old in db.scalars(select(ReviewItem).where(ReviewItem.candidate_id == cand.id)):
            db.delete(old)
        items = fields_to_review(profile, get_settings().review_threshold, failed)
        for field, value, conf in items:
            db.add(ReviewItem(candidate_id=cand.id, field=field, value=value, confidence=conf))
        new_stage = Stage.REVIEW if items or failed else Stage.EXTRACTED
        reason = cand.error or f"{cand.cv_format}: {len(items)} field(s) to review"
        db.add(DecisionLog(actor="system", action="cv read", subject=f"candidate:{cand.id}", reason=reason))
        move(db, cand, new_stage, "system", reason)
        db.commit()
    finally:
        db.close()


# ---- the recruiter's review queue (Prompt 12) -----------------------------------------------------------------
LIST_FIELDS = {"jobs", "skills", "certifications"}


def parse_value(field: str, raw: str):
    """Text from a form back into a value: lists are separated by semicolons, years are a number."""
    raw = (raw or "").strip()
    if field in LIST_FIELDS:
        return [x.strip() for x in raw.split(";") if x.strip()] or None
    if field == "years_experience":
        return float(raw) if raw else None
    return raw or None


def correct_fields(db, cand: Candidate, submitted: dict[str, str], actor: str) -> list[str]:
    """Saves what the recruiter typed. Every field they were shown is now checked by a person (confidence 1.0).
    Changed fields are logged with the value before and after; years are recalculated if the jobs changed."""
    from copy import deepcopy

    from app.agents.document import apply_years

    profile = CandidateProfile.model_validate(cand.profile or {})
    before = deepcopy(profile)
    changed: list[str] = []
    old_text = {f: value_text(getattr(profile, f).value) for f in submitted}
    for field, raw in submitted.items():
        if field == "years_experience":
            continue
        value = parse_value(field, raw)
        f = getattr(profile, field)
        if value_text(value) != old_text[field]:
            changed.append(field)
        f.value, f.confidence = value, 1.0
    if "jobs" in changed or "years_experience" in submitted:
        years_typed = "years_experience" in submitted and submitted["years_experience"].strip() != old_text["years_experience"].strip()
        if years_typed and "jobs" not in changed:
            profile.years_experience.value = parse_value("years_experience", submitted["years_experience"])
            profile.years_experience.confidence = 1.0
            changed.append("years_experience")
        else:
            apply_years(profile)
            profile.years_experience.confidence = 1.0
            if value_text(profile.years_experience.value) != old_text.get("years_experience", value_text(before.years_experience.value)):
                changed.append("years_experience")
    cand.profile = profile.model_dump()
    for item in db.scalars(select(ReviewItem).where(ReviewItem.candidate_id == cand.id, ReviewItem.field.in_(submitted),
                                                    ReviewItem.resolved.is_(False))):
        item.resolved = True
    for field in dict.fromkeys(changed):
        db.add(DecisionLog(actor=actor, action=f"corrected {field}", subject=f"candidate:{cand.id}",
                           reason="checked by a person in the review queue",
                           evidence={"before": value_text(getattr(before, field).value),
                                     "after": value_text(getattr(profile, field).value)}))
    db.add(DecisionLog(actor=actor, action="review saved", subject=f"candidate:{cand.id}",
                       reason=f"{len(submitted)} field(s) checked, {len(set(changed))} changed"))
    return list(dict.fromkeys(changed))
