"""Shortlist (Day 2): the system SUGGESTS a ranked list with strengths and gaps; a recruiter APPROVES it (rule 1).

Approving moves each chosen candidate SCREENED -> SHORTLISTED through the supervisor, with the recruiter's reason and the
scores they saw as evidence. Nobody is shortlisted by this module on its own.
"""
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Candidate, DecisionLog, Requisition
from app.models_ext import ItemScoreRow, ShortlistEntry
from app.schemas import Stage
from app.supervisor import MoveRefused, move


def scores_for(db: Session, req_id: int, cand_id: int) -> list[ItemScoreRow]:
    return list(db.scalars(select(ItemScoreRow).where(ItemScoreRow.requisition_id == req_id, ItemScoreRow.candidate_id == cand_id).order_by(ItemScoreRow.id)))


def weighted_total(rows: list[ItemScoreRow]) -> float:
    return round(sum(r.weight * r.score for r in rows) / 3, 1)


def suggest_shortlist(db: Session, req_id: int, top_n: int = 5) -> list[ShortlistEntry]:
    req = db.get(Requisition, req_id)
    must = {i["skill"] for i in (req.rubric or {}).get("items", []) if i["must_have"]}
    db.execute(delete(ShortlistEntry).where(ShortlistEntry.requisition_id == req_id))
    rows = []
    for cand in db.scalars(select(Candidate).where(Candidate.requisition_id == req_id, Candidate.stage.in_(["SCREENED", "SHORTLISTED"]))):
        sc = scores_for(db, req_id, cand.id)
        if not sc:
            continue
        held = any(r.status == "returned" for r in sc)  # sent back by the compliance reviewer: not shown as suggested
        missing = [r.skill for r in sc if r.skill in must and r.score == 0]
        strengths = [f"{r.skill} ({r.score}/3): \"{r.quote}\"" for r in sorted(sc, key=lambda r: -r.weight * r.score) if r.score >= 2][:3]
        gaps = [f"{r.skill}: " + ("no evidence" if r.score == 0 else f"only mentioned ({r.score}/3)") + (" (must-have)" if r.skill in must else "")
                for r in sc if r.score <= 1 and (r.skill in must or r.score == 0)]
        if held:
            gaps = ["held by the compliance reviewer: a score was sent back for a missing quote"] + gaps
        rows.append((held, bool(missing), -weighted_total(sc), cand.id, weighted_total(sc), strengths, gaps))
    rows.sort()  # held candidates last; then those with every must-have first, then by weighted total, then by id (stable)
    entries = []
    for rank, (held, _missing, _neg, cid, total, strengths, gaps) in enumerate(rows, 1):
        e = ShortlistEntry(requisition_id=req_id, candidate_id=cid, rank=rank, weighted_total=total, strengths=strengths, gaps=gaps,
                           status="HELD" if held else ("SUGGESTED" if rank <= top_n else "NOT_SELECTED"))
        db.add(e)
        entries.append(e)
    db.add(DecisionLog(actor="system", action="shortlist suggested", subject=f"requisition:{req_id}",
                       reason=f"{len(entries)} ranked, top {top_n} suggested: waiting for a recruiter to approve"))
    db.commit()
    return entries


def approve_shortlist(db: Session, req_id: int, candidate_ids: list[int], actor: str, reason: str) -> list[int]:
    """A person approves the shortlist. Every chosen candidate moves SCREENED -> SHORTLISTED with the reason and the scores seen."""
    if not (reason or "").strip():
        raise MoveRefused("Approving a shortlist needs a reason.")
    moved = []
    for cid in candidate_ids:
        cand = db.get(Candidate, cid)
        if cand is None or cand.requisition_id != req_id:
            raise MoveRefused(f"Candidate {cid} is not an applicant for this job.")
        sc = scores_for(db, req_id, cid)
        unverified = [r.skill for r in sc if r.score > 0 and (not r.verified or r.status == "returned")]
        if unverified:
            raise MoveRefused(f"Candidate {cid} has scores without a verified quote ({', '.join(unverified)}): they cannot be approved.")
        move(db, cand, Stage.SHORTLISTED, actor, reason,
             evidence={"weighted_total": weighted_total(sc), "scores": {r.skill: {"score": r.score, "quote": r.quote} for r in sc}})
        moved.append(cid)
    for e in db.scalars(select(ShortlistEntry).where(ShortlistEntry.requisition_id == req_id)):
        e.status = "APPROVED" if e.candidate_id in moved else "NOT_SELECTED"
    db.add(DecisionLog(actor=actor, action="shortlist approved", subject=f"requisition:{req_id}", reason=reason.strip(),
                       evidence={"candidates": moved}))
    db.commit()
    return moved
