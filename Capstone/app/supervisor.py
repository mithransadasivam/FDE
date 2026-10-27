"""The supervisor: which stage moves are allowed, who may make them, and the log of every move (Prompt 13).

Rule 1: a person decides. The system may make automatic steps (reading a CV, scoring); only a person may make a
decision (shortlisting and everything after it, or withdrawing). move() is the ONLY code that changes a candidate's
stage, so even an agent that tries to shortlist on Day 2 is refused here.
"""
from sqlalchemy.orm import Session

from app.models import Candidate, DecisionLog
from app.schemas import Stage

SYSTEM = "system"  # an automatic step
PERSON = "person"  # a decision: only a person may make it

ALLOWED: dict[Stage, dict[Stage, str]] = {
    Stage.APPLIED: {Stage.EXTRACTED: SYSTEM, Stage.REVIEW: SYSTEM, Stage.WITHDRAWN: PERSON},
    Stage.REVIEW: {Stage.EXTRACTED: PERSON, Stage.WITHDRAWN: PERSON},
    Stage.EXTRACTED: {Stage.SCREENED: SYSTEM, Stage.WITHDRAWN: PERSON},
    Stage.SCREENED: {Stage.SHORTLISTED: PERSON, Stage.WITHDRAWN: PERSON},
    # SHORTLISTED -> HUMAN_INTERVIEW is only for a candidate who asked for a person instead of the AI interviewer (policy 4.4): see GUARDS
    Stage.SHORTLISTED: {Stage.AI_INTERVIEW: PERSON, Stage.HUMAN_INTERVIEW: PERSON, Stage.WITHDRAWN: PERSON},
    Stage.AI_INTERVIEW: {Stage.HUMAN_INTERVIEW: PERSON, Stage.WITHDRAWN: PERSON},
    Stage.HUMAN_INTERVIEW: {Stage.DECISION: PERSON, Stage.WITHDRAWN: PERSON},
    Stage.DECISION: {Stage.WITHDRAWN: PERSON},
    Stage.WITHDRAWN: {},
}


# Extra conditions on a few moves. The condition must be shown in the move's evidence, so it is on the record.
GUARDS = {(Stage.SHORTLISTED, Stage.HUMAN_INTERVIEW): ("asked_for_person", "A candidate can skip the AI interview only if they asked for a person instead.")}


class MoveRefused(Exception):
    """The move is not allowed. The message says why and what is allowed instead, so it can be shown to a person."""


def allowed_from(stage: Stage | str) -> dict[Stage, str]:
    return ALLOWED.get(Stage(stage), {})


def move(db: Session, cand: Candidate, to: Stage | str, actor: str, reason: str = "", evidence: dict | list | None = None) -> Stage:
    """Moves a candidate to another stage, or raises MoveRefused. Every move is written to the decision log."""
    try:
        to = Stage(to)
    except ValueError:
        raise MoveRefused(f"'{to}' is not a stage. The stages are: {', '.join(s.value for s in Stage)}.") from None
    frm = Stage(cand.stage)
    who = allowed_from(frm).get(to)
    if who is None:
        options = ", ".join(s.value for s in allowed_from(frm)) or "nowhere: this candidate's process has ended"
        raise MoveRefused(f"Moving from {frm.value} to {to.value} is not allowed. From {frm.value} a candidate can go to: {options}.")
    if who == PERSON and actor == SYSTEM:
        raise MoveRefused(f"Moving from {frm.value} to {to.value} is a decision, and only a person can make it. "
                          f"The system can suggest it, but a person must approve it.")
    if who == PERSON and not (reason or "").strip():
        raise MoveRefused(f"A person's move needs a reason: say why you are moving the candidate from {frm.value} to {to.value}.")
    guard = GUARDS.get((frm, to))
    if guard and not (evidence or {}).get(guard[0]):
        raise MoveRefused(f"Moving from {frm.value} to {to.value} is not allowed here. {guard[1]} Invite them to the AI interview first.")
    cand.stage = to.value
    db.add(DecisionLog(actor=actor, action=f"move {frm.value} -> {to.value}", subject=f"candidate:{cand.id}",
                       reason=(reason or "").strip(), evidence=evidence))
    return to
