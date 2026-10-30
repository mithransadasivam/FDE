"""The three stages side by side for one candidate (Day 4, prompt 1). Everything here is read from what is already stored: nothing is generated.

Screening is scored 0-3 per skill, the AI interview and the human interview 0-3 as well in this build (the question bank's own scale). Where two stages
differ by 2 or more the row says so, so a person looks at the evidence for both.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.credentials import credential_checks
from app.interview import recording
from app.models import Candidate, Requisition
from app.models_ext import EvidenceCheck, HumanInterview, InterviewSession, ItemScoreRow

DIFFER_BY = 2


def replay_ready(db: Session, cand_id: int) -> InterviewSession | None:
    """The interview if its replay can open (finished, consent, the recruiter's own review done, recording built)."""
    s = db.query(InterviewSession).filter_by(candidate_id=cand_id).first()
    if s is None or s.status != "DONE" or not s.consent_recording or not s.review:
        return None
    if not recording.mp3_path(s).exists() or recording.load_timeline(s) is None:
        return None
    return s


def stage_summary(db: Session, cand: Candidate) -> dict:
    from app.interview.scorecard import build_card

    req = db.get(Requisition, cand.requisition_id)
    items = (req.rubric or {}).get("items", [])
    cv = {r.skill: r for r in db.scalars(select(ItemScoreRow).where(ItemScoreRow.candidate_id == cand.id))}
    s = db.query(InterviewSession).filter_by(candidate_id=cand.id).first()
    ai_card = build_card(db, s) if s and s.status == "DONE" and s.scorecard else None
    ai = {r["skill"]: r for r in (ai_card or {}).get("skills", [])}
    hi = db.scalars(select(HumanInterview).where(HumanInterview.candidate_id == cand.id).order_by(HumanInterview.id.desc())).first()
    human, suggestion, points, conflicts = {}, {}, {}, (hi.draft_scorecard or {}).get("cv_checks", []) if hi else []
    if hi and hi.draft_scorecard:
        for a in hi.draft_scorecard.get("answers", []):
            if a.get("type") != "technical":
                continue
            suggestion[a["skill"]] = a.get("suggested_score")
            points[a["skill"]] = len(a.get("points_hit") or [])
            lv = ((hi.recruiter_scores or {}).get("scores") or {}).get(a["question_id"])
            if lv is not None:
                human[a["skill"]] = int(lv)
    ready = replay_ready(db, cand.id)
    timeline = recording.load_timeline(ready) if ready else None
    rows = []
    for it in items:
        sk = it["skill"]
        cvr, air = cv.get(sk), ai.get(sk)
        levels = [v for v in (cvr.score if cvr else None, air["level"] if air else None, human.get(sk)) if v is not None]
        best = (air or {}).get("best") or {}
        rows.append({"skill": sk, "must_have": bool(it.get("must_have")), "weight": it.get("weight"),
                     "screening": cvr.score if cvr else None, "ai": air["level"] if air and air["asked"] else None, "human": human.get(sk),
                     "differ": len(levels) >= 2 and max(levels) - min(levels) >= DIFFER_BY,
                     "cv_quote": cvr.quote if cvr else None, "cv_verified": bool(cvr and cvr.verified),
                     "ai_questions": (air or {}).get("questions", []), "ai_quote": best.get("quote"), "ai_play_t": recording.moment_time(timeline, best.get("quote")),
                     "hints": (air or {}).get("hints", 0), "follow_ups": (air or {}).get("follow_ups", 0),
                     "human_ai_suggestion": suggestion.get(sk), "human_points_heard": points.get(sk)})
    checks = list(db.scalars(select(EvidenceCheck).where(EvidenceCheck.candidate_id == cand.id)))
    return {"rows": rows, "replay": bool(ready), "credentials": credential_checks(cand.profile), "cv_conflicts": [(c.get("text") or c.get("question") or "") if isinstance(c, dict) else str(c) for c in conflicts],
            "checks": [{"subject": c.subject, "status": c.status, "acknowledged": bool(getattr(c, "acknowledged_by", None))} for c in checks]}
