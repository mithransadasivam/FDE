"""Compliance reviewer (Day 3): checks the other agents' work before the recruiter relies on it, and sends bad work back.

 check_evidence   every score's quote must really be in its source (the CV text or the interview transcript)
 scan_prompt_log  no identity detail or protected trait may appear in any scoring prompt
 check_log        the decision log must be complete: every decision has a person, a reason and a matching record
Its findings go to the recruiter. It never decides anything itself.
"""
import json

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import guardrails
from app.agents.base import BaseAgent, register_tool
from app.db import OpsSession
from app.evidence import blind_text, quote_exists
from app.models import Candidate, DecisionLog, Requisition
from app.models_ext import ComplianceFinding, InterviewSession, ItemScoreRow, ModelCall, OutboxLog
from app.privacy import identity_strings, make_blind
from app.schemas import Finding

SCORING_AGENTS = ("screening", "interviewer", "copilot")
PERSON_STAGES = {"SHORTLISTED", "AI_INTERVIEW", "HUMAN_INTERVIEW", "DECISION", "WITHDRAWN"}


class EvidenceArgs(BaseModel):
    requisition_id: int | None = None


class PromptArgs(BaseModel):
    since_id: int = 0


class LogArgs(BaseModel):
    pass


# ---- the three checks ----------------------------------------------------------------------------------------------------------------
@register_tool("check_evidence", EvidenceArgs, "Check that every score has a quote that really is in its source")
def check_evidence(args: EvidenceArgs, ctx: dict) -> list[dict]:
    db: Session = ctx["db"]
    findings: list[Finding] = []
    q = select(ItemScoreRow)
    if args.requisition_id:
        q = q.where(ItemScoreRow.requisition_id == args.requisition_id)
    sources: dict[int, str] = {}
    for row in db.scalars(q):
        if row.score <= 0:
            continue
        if row.candidate_id not in sources:
            cand = db.get(Candidate, row.candidate_id)
            sources[row.candidate_id] = blind_text(make_blind(cand)) if cand else ""
        if not row.quote.strip() or not quote_exists(row.quote, sources[row.candidate_id]):
            findings.append(Finding(check="quote not in source", candidate_id=row.candidate_id,
                                    detail=f"{row.skill}: score {row.score} cites \"{row.quote[:80]}\", which is not in the CV text. Sent back."))
            row.status, row.verified = "returned", False  # sends the work back: it cannot be approved until it is scored again
    for s in db.scalars(select(InterviewSession).where(InterviewSession.scorecard.is_not(None))):
        said = {t["question_id"]: " ".join(a["text"] for a in t["answers"]) for t in (s.state or {}).get("turns", [])}
        for a in s.scorecard.get("answers", []):
            if a.get("score", 0) > 0 and not quote_exists(a.get("quote", ""), said.get(a["question_id"], "")):
                findings.append(Finding(check="interview quote not in transcript", candidate_id=s.candidate_id,
                                        detail=f"{a['question_id']}: score {a['score']} cites \"{a.get('quote', '')[:80]}\", which is not in the transcript."))
    return [f.model_dump() for f in findings]


@register_tool("scan_prompt_log", PromptArgs, "Scan the prompt log for identity details or protected traits in scoring prompts")
def scan_prompt_log(args: PromptArgs, ctx: dict) -> list[dict]:
    db: Session = ctx["db"]
    findings: list[Finding] = []
    with OpsSession() as ops:
        calls = ops.scalars(select(ModelCall).where(ModelCall.agent.in_(SCORING_AGENTS), ModelCall.id > args.since_id)).all()
    names: dict[int, list[str]] = {}
    for c in calls:
        if c.candidate_id not in names:
            cand = db.get(Candidate, c.candidate_id) if c.candidate_id else None
            names[c.candidate_id] = identity_strings(cand.profile or {}) if cand else []
        # the system prompt and the fixed question text are ours; the candidate-controlled parts are scanned
        hits = guardrails.scan_protected(c.prompt_user, names[c.candidate_id])
        if hits:
            findings.append(Finding(check="protected detail in scoring prompt", candidate_id=c.candidate_id,
                                    detail=f"{c.agent} prompt #{c.id} contains " + ", ".join(sorted({f'{k} ("{v[:30]}")' for k, v in hits})[:4])))
    return [f.model_dump() for f in findings]


@register_tool("check_log", LogArgs, "Check the decision log is complete: every decision has a person, a reason and a matching record")
def check_log(args: LogArgs, ctx: dict) -> list[dict]:
    db: Session = ctx["db"]
    findings: list[Finding] = []
    logs = list(db.scalars(select(DecisionLog).order_by(DecisionLog.id)))
    moves: dict[str, list[DecisionLog]] = {}
    for e in logs:
        if e.action.startswith("move "):
            moves.setdefault(e.subject, []).append(e)
            target = e.action.split("-> ")[-1]
            if target in PERSON_STAGES or e.action == "move REVIEW -> EXTRACTED":
                if "@" not in e.actor:
                    findings.append(Finding(check="decision without a person", detail=f"{e.action} on {e.subject} was made by '{e.actor}', not a person"))
                if not (e.reason or "").strip():
                    findings.append(Finding(check="decision without a reason", detail=f"{e.action} on {e.subject} has no reason"))
    for c in db.scalars(select(Candidate)):
        ms = moves.get(f"candidate:{c.id}", [])
        last = ms[-1].action.split("-> ")[-1] if ms else "APPLIED"
        if last != c.stage:
            findings.append(Finding(check="stage without a logged move", candidate_id=c.id, detail=f"candidate is in {c.stage} but the last logged move leads to {last}"))
    for r in db.scalars(select(Requisition).where(Requisition.status.in_(["APPROVED", "PUBLISHED"]))):
        if not any(e.action == "rubric approved" and e.subject == f"requisition:{r.id}" and "@" in e.actor for e in logs):
            findings.append(Finding(check="rubric approval missing", detail=f"requisition {r.id} is {r.status} but no person's approval is logged"))
    for o in db.scalars(select(OutboxLog)):
        if "@" not in o.approved_by or not any(e.action.startswith("email approved") and (e.evidence or {}).get("draft_id") == o.draft_id for e in logs):
            findings.append(Finding(check="email sent without a logged approval", candidate_id=o.to_candidate, detail=f"outbox entry {o.id} has no person's approval in the decision log"))
    return [f.model_dump() for f in findings]


class ComplianceAgent(BaseAgent):
    name = "compliance"


def review(db: Session, requisition_id: int | None = None) -> list[ComplianceFinding]:
    """Runs all three checks and stores NEW open findings. The recruiter sees them on the Compliance page."""
    agent = ComplianceAgent(db)
    raw = (agent.call("check_evidence", requisition_id=requisition_id) + agent.call("scan_prompt_log")
           + agent.call("check_log"))
    existing = {(f.check, f.candidate_id, f.detail) for f in db.scalars(select(ComplianceFinding).where(ComplianceFinding.status == "OPEN"))}
    new = []
    for f in raw:
        key = (f["check"], f["candidate_id"], f["detail"])
        if key not in existing:
            row = ComplianceFinding(check=f["check"], severity=f["severity"], detail=f["detail"], candidate_id=f["candidate_id"])
            db.add(row)
            new.append(row)
    db.add(DecisionLog(actor="system", action="compliance review", subject=f"requisition:{requisition_id or 'all'}",
                       reason=f"{len(raw)} finding(s), {len(new)} new; recruiter to read them"))
    db.commit()
    return new


def open_findings(db: Session) -> list[ComplianceFinding]:
    return list(db.scalars(select(ComplianceFinding).where(ComplianceFinding.status == "OPEN").order_by(ComplianceFinding.id)))
