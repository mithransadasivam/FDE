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
        db.add(DecisionLog(actor="system", action="cv read", subject=f"candidate:{cand.id}",
                           reason=(cand.error or f"{cand.cv_format}: {len(items)} field(s) to review")))
        cand.stage = new_stage.value
        db.add(DecisionLog(actor="system", action=f"move {Stage.APPLIED.value} -> {new_stage.value}", subject=f"candidate:{cand.id}"))
        db.commit()
    finally:
        db.close()
