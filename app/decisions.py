"""The scorecard and the final decision (Day 4, BR-15 and BR-19).

build_scorecard gathers everything about one candidate in one place, with the evidence behind every number. The AI only RECOMMENDS;
decide() records a PERSON's decision and reason, moves the candidate through the supervisor, and drafts the email (which still waits
for a person's approval). explain_not_shortlisted() drafts the plain explanation a candidate can ask for, for a recruiter to review.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.communications import CommsAgent, draft_decision
from app.models import Candidate, DecisionLog, Requisition
from app.models_ext import (ComplianceFinding, EmailDraft, ExplanationRequest, FinalDecision, Flag, HumanInterview, InterviewSession, ItemScoreRow)
from app.schemas import Decision, Stage
from app.supervisor import MoveRefused, move

DECISIONS = {"ADVANCE": "advance", "OFFER_RECOMMENDED": "advance", "HOLD": "hold", "NOT_THIS_TIME": "decline"}


def recommendation(scores: list[ItemScoreRow], ai_total: float | None) -> str:
    """What the AI suggests. It is a suggestion: the recruiter decides."""
    if not scores:
        return "Not scored yet."
    weak = [r.skill for r in sorted(scores, key=lambda r: (r.score, -r.weight)) if r.score <= 1][:2]
    total = round(sum(r.weight * r.score for r in scores) / 3, 1)
    lead = "move to a human interview" if total >= 60 and (ai_total is None or ai_total >= 1.5) else "consider holding or a closer look before going further"
    probe = f" Probe {' and '.join(weak).lower()}." if weak else ""
    return f"Recommendation: {lead}.{probe} (CV score {total}/100" + (f", AI interview {ai_total}/3" if ai_total is not None else "") + ")"


def build_scorecard(db: Session, cand: Candidate) -> dict:
    req = db.get(Requisition, cand.requisition_id)
    scores = list(db.scalars(select(ItemScoreRow).where(ItemScoreRow.candidate_id == cand.id).order_by(ItemScoreRow.id)))
    ai = db.scalars(select(InterviewSession).where(InterviewSession.candidate_id == cand.id)).first()
    hi = db.scalars(select(HumanInterview).where(HumanInterview.candidate_id == cand.id).order_by(HumanInterview.id.desc())).first()
    ai_card = ai.scorecard if ai and ai.scorecard else None
    findings = list(db.scalars(select(ComplianceFinding).where(ComplianceFinding.candidate_id == cand.id)))
    quotes_checked = all(r.verified and r.status == "ok" for r in scores if r.score > 0)
    human = None
    if hi and hi.draft_scorecard:
        human = {"draft": hi.draft_scorecard, "recruiter_scores": hi.recruiter_scores, "recording": hi.recording, "status": hi.status,
                 "moments": [{"t": e["t"], "q": e["data"]["question_id"], "quote": p["quote"], "point": p["text"]}
                             for e in (hi.events or []) if e["kind"] == "key_point" for p in e["data"]["points"]]}
    return {
        "candidate_id": cand.id, "stage": cand.stage, "job": (req.job or {}).get("title") or req.title,
        "cv_scores": [{"skill": r.skill, "weight": r.weight, "score": r.score, "quote": r.quote, "verified": r.verified, "status": r.status} for r in scores],
        "cv_total": round(sum(r.weight * r.score for r in scores) / 3, 1) if scores else None,
        "ai_interview": ai_card, "ai_status": ai.status if ai else None, "ai_reviewed_by": ai.reviewed_by if ai else None,
        "human_interview": human,
        "checks": {"every_score_has_a_quote": quotes_checked, "protected_traits_in_prompts": not any(f.check == "protected detail in scoring prompt" and f.status == "OPEN" for f in findings),
                   "open_findings": [f.detail for f in findings if f.status == "OPEN"],
                   "compliance_reviewer": "passed" if quotes_checked and not any(f.status == "OPEN" for f in findings) else "findings open"},
        "flags": [{"kind": f.kind, "detail": f.detail} for f in db.scalars(select(Flag).where(Flag.candidate_id == cand.id))],
        "decision": next(({"decision": d.decision, "reason": d.reason, "actor": d.actor, "at": str(d.at)} for d in db.scalars(select(FinalDecision).where(FinalDecision.candidate_id == cand.id).order_by(FinalDecision.id.desc()))), None),
        "recommendation": recommendation(scores, (ai_card or {}).get("total")),
        "emails": [{"id": e.id, "kind": e.kind, "subject": e.subject, "status": e.status} for e in db.scalars(select(EmailDraft).where(EmailDraft.candidate_id == cand.id))],
    }


def decide(db: Session, cand: Candidate, decision: str, reason: str, actor: str) -> FinalDecision:
    """A person's final decision. It needs a reason, is logged with the evidence the person saw, moves the candidate to DECISION through the
    supervisor, and drafts an email that still waits in the outbox for approval."""
    d = Decision(candidate_id=cand.id, decision=decision, reason=(reason or "").strip() or "x", actor=actor)  # validates the shape
    if decision not in DECISIONS:
        raise MoveRefused(f"'{decision}' is not a decision. Choose one of: {', '.join(DECISIONS)}.")
    if not (reason or "").strip() or len(reason.strip()) < 3:
        raise MoveRefused("A decision needs a reason.")
    card = build_scorecard(db, cand)
    if cand.stage == Stage.HUMAN_INTERVIEW.value:
        move(db, cand, Stage.DECISION, d.actor, f"{decision}: {reason.strip()}", evidence={"scorecard": {k: card[k] for k in ("cv_total", "recommendation", "checks")}})
    elif cand.stage != Stage.DECISION.value:
        raise MoveRefused(f"A final decision is made after the human interview. This candidate is in {cand.stage}.")
    row = FinalDecision(candidate_id=cand.id, decision=decision, reason=reason.strip(), actor=actor, evidence=card)
    db.add(row)
    db.add(DecisionLog(actor=actor, action=f"final decision: {decision}", subject=f"candidate:{cand.id}", reason=reason.strip(), evidence=card))
    draft_decision(db, cand, DECISIONS[decision])
    return row


def explain_not_shortlisted(db: Session, cand: Candidate) -> ExplanationRequest:
    """A candidate asked why they were not shortlisted. Drafts a plain explanation built from the evidence (their own scores and quotes),
    for a recruiter to review before anything is sent (BR-19)."""
    scores = list(db.scalars(select(ItemScoreRow).where(ItemScoreRow.candidate_id == cand.id)))
    if not scores:
        raise MoveRefused("There is nothing to explain yet: your application has not been compared with the role.")
    strengths = [f"your CV showed {r.skill.lower()} (\"{r.quote}\")" for r in sorted(scores, key=lambda r: -r.weight * r.score) if r.score >= 2][:2]
    gaps = [r.skill.lower() for r in sorted(scores, key=lambda r: (r.score, -r.weight)) if r.score <= 1][:3]
    extra = {"strengths": ("In your favour: " + "; ".join(strengths) + ".") if strengths else "",
             "gaps": ("Other applications showed more evidence of: " + ", ".join(gaps) + ".") if gaps else ""}
    agent = CommsAgent(db, cand.id)
    draft_id = agent.call("draft_email", candidate_id=cand.id, kind="explanation", extra=extra)["draft_id"]
    req = ExplanationRequest(candidate_id=cand.id, draft_id=draft_id, status="WAITING_FOR_RECRUITER")
    db.add(req)
    db.add(DecisionLog(actor="candidate", action="asked why not shortlisted", subject=f"candidate:{cand.id}", reason="an explanation was drafted for a recruiter to review"))
    return req
