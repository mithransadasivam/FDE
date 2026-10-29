"""Hiring analytics: the funnel, score spread, interview quality and cost, computed from the data the platform already keeps (nothing new is collected).

Everything here is about the PROCESS (how many people are where, how the scoring is behaving), never about a person's protected traits: the platform does not
hold age, gender or origin, and the analytics do not try to infer them.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import OpsSession
from app.models import Candidate, DecisionLog, Requisition
from app.models_ext import InterviewSession, ItemScoreRow, ModelCall, OutboxLog
from app.schemas import Stage

FUNNEL_ORDER = [Stage.APPLIED, Stage.EXTRACTED, Stage.SCREENED, Stage.SHORTLISTED, Stage.AI_INTERVIEW, Stage.HUMAN_INTERVIEW, Stage.DECISION]


def _aware(dt: datetime | None) -> datetime | None:
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _candidates(db: Session, req_id: int | None) -> list[Candidate]:
    q = select(Candidate)
    if req_id:
        q = q.where(Candidate.requisition_id == req_id)
    return list(db.scalars(q))


def visited_stages(db: Session, cands: list[Candidate]) -> dict[int, set[str]]:
    """Every stage each candidate has ever been in, from the decision log of moves (plus the stage they are in now)."""
    ids = {c.id for c in cands}
    seen: dict[int, set[str]] = {c.id: {Stage.APPLIED.value, c.stage} for c in cands}
    for e in db.scalars(select(DecisionLog).where(DecisionLog.action.like("move %"))):
        if e.subject.startswith("candidate:"):
            cid = int(e.subject.split(":")[1])
            if cid in ids:
                a, b = e.action[5:].split(" -> ")
                seen[cid] |= {a, b}
    for s in seen.values():  # REVIEW is a side-step before EXTRACTED: it counts as extracted
        if Stage.REVIEW.value in s:
            s.add(Stage.EXTRACTED.value)
    return seen


def funnel(db: Session, req_id: int | None = None) -> list[dict]:
    """How many candidates reached each stage, and the share of the previous stage that went on."""
    cands = _candidates(db, req_id)
    seen = visited_stages(db, cands)
    rows, prev = [], None
    for st in FUNNEL_ORDER:
        n = sum(1 for s in seen.values() if st.value in s)
        rows.append({"stage": st.value, "n": n, "of_previous": round(100 * n / prev, 1) if prev else None, "of_applied": round(100 * n / max(1, len(cands)), 1)})
        prev = n or prev
    return rows


def current_stages(db: Session, req_id: int | None = None) -> dict[str, int]:
    return dict(Counter(c.stage for c in _candidates(db, req_id)))


def score_distribution(db: Session, req_id: int | None = None, bins: int = 10) -> list[dict]:
    """The spread of CV scores (out of 100) in bands of 10: a quick check that the rubric separates candidates."""
    q = select(ItemScoreRow.candidate_id, func.sum(ItemScoreRow.weight * ItemScoreRow.score)).group_by(ItemScoreRow.candidate_id)
    if req_id:
        q = q.where(ItemScoreRow.requisition_id == req_id)
    totals = [round(float(t) / 3, 1) for _cid, t in db.execute(q).all()]
    width = 100 // bins
    out = [{"from": i * width, "to": (i + 1) * width, "n": 0} for i in range(bins)]
    for t in totals:
        out[min(bins - 1, int(t // width))]["n"] += 1
    return out


def time_to_move(db: Session, req_id: int | None = None) -> list[dict]:
    """Average hours from APPLIED to each stage, from the log's timestamps (demo data is created in minutes, real data in days)."""
    cands = {c.id: c for c in _candidates(db, req_id)}
    first: dict[tuple[int, str], datetime] = {}
    for e in db.scalars(select(DecisionLog).where(DecisionLog.action.like("move %")).order_by(DecisionLog.id)):
        if e.subject.startswith("candidate:") and int(e.subject.split(":")[1]) in cands:
            first.setdefault((int(e.subject.split(":")[1]), e.action.split(" -> ")[-1]), _aware(e.at))
    out = []
    for st in (Stage.SCREENED, Stage.SHORTLISTED, Stage.AI_INTERVIEW, Stage.HUMAN_INTERVIEW):
        hours = [(first[(cid, st.value)] - _aware(c.applied_at)).total_seconds() / 3600 for cid, c in cands.items() if (cid, st.value) in first and c.applied_at]
        out.append({"stage": st.value, "n": len(hours), "avg_hours": round(sum(hours) / len(hours), 2) if hours else None})
    return out


def interview_stats(db: Session, req_id: int | None = None) -> dict:
    from app.interview.scorecard import build_card

    rows = [s for s in db.scalars(select(InterviewSession)) if not req_id or db.get(Candidate, s.candidate_id).requisition_id == req_id]
    done = [s for s in rows if s.status == "DONE" and s.scorecard]
    overall, minutes, disagree, flagged, recorded = [], [], 0, 0, 0
    for s in done:
        card = build_card(db, s)
        overall.append(card["overall_100"])
        minutes.append(((s.state or {}).get("elapsed_s", 0)) / 60)
        if card["scorers_disagree"]:
            flagged += 1
        disagree += len(card["scorers_disagree"])
        recorded += 1 if s.recording_built_at else 0
    return {"invited": len(rows), "done": len(done), "asked_for_person": sum(1 for s in rows if s.status == "PERSON_REQUESTED"),
            "avg_overall": round(sum(overall) / len(overall), 1) if overall else None, "avg_minutes": round(sum(minutes) / len(minutes), 1) if minutes else None,
            "with_scorer_disagreement": flagged, "recordings": recorded, "reviewed_by_a_person": sum(1 for s in done if s.reviewed_by),
            "samples": sum(1 for s in rows if s.sample)}


def cost_stats(db: Session, req_id: int | None = None) -> dict:
    """What the model calls cost (in fake mode: what they WOULD have cost), per candidate screened and per interview."""
    with OpsSession() as ops:
        by_agent = defaultdict(float)
        for agent, cost in ops.execute(select(ModelCall.agent, func.sum(ModelCall.cost_usd)).group_by(ModelCall.agent)).all():
            by_agent[agent] = float(cost or 0)
        simulated = bool(ops.scalar(select(func.count()).select_from(ModelCall).where(ModelCall.simulated.is_(True))))
    screened = db.scalar(select(func.count(func.distinct(ItemScoreRow.candidate_id)))) or 0
    done = db.scalar(select(func.count()).select_from(InterviewSession).where(InterviewSession.status == "DONE")) or 0
    return {"by_agent": dict(by_agent), "total": round(sum(by_agent.values()), 4), "simulated": simulated,
            "per_cv": round(by_agent.get("screening", 0) / screened, 5) if screened else None,
            "per_interview": round(by_agent.get("interviewer", 0) / done, 4) if done else None}


def people_in_the_loop(db: Session) -> dict:
    """The human-oversight numbers a buyer's compliance team asks for: decisions made by people, emails approved by people."""
    moves = list(db.scalars(select(DecisionLog).where(DecisionLog.action.like("move %"))))
    person = [m for m in moves if "@" in m.actor]
    return {"moves": len(moves), "by_a_person": len(person), "by_the_system": len(moves) - len(person),
            "emails_sent": db.scalar(select(func.count()).select_from(OutboxLog)) or 0,
            "with_reason": sum(1 for m in person if (m.reason or "").strip())}


def everything(db: Session, req_id: int | None = None) -> dict:
    reqs = db.scalars(select(Requisition).where(Requisition.status.in_(["APPROVED", "PUBLISHED"])).order_by(Requisition.id)).all()
    return {"funnel": funnel(db, req_id), "stages": current_stages(db, req_id), "scores": score_distribution(db, req_id), "time": time_to_move(db, req_id),
            "interviews": interview_stats(db, req_id), "cost": cost_stats(db, req_id), "oversight": people_in_the_loop(db), "requisitions": reqs, "req_id": req_id}
