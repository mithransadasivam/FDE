"""The scorecard (one per candidate) and the recruiter's logged decision."""
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import RECRUITER, STAFF
from app.db import get_db
from app.decisions import DECISIONS, build_scorecard, decide
from app.models import Candidate, DecisionLog, User
from app.stages import stage_summary
from app.supervisor import MoveRefused
from app.web.common import flash, render

router = APIRouter(prefix="/scorecard")
alias = APIRouter()  # /candidates/<id>/scorecard: the same page, under the candidate


def _show(request: Request, cand_id: int, user: User, db: Session):
    cand = db.get(Candidate, cand_id)
    if cand is None:
        raise HTTPException(404, "That candidate does not exist")
    db.add(DecisionLog(actor=user.email, action="scorecard opened", subject=f"candidate:{cand.id}", reason=f"{user.role} opened the scorecard",
                       evidence={"blind": user.role == "hiring_manager"}))
    db.commit()
    return render(request, "scorecard.html", user, cand=cand, card=build_scorecard(db, cand), stages=stage_summary(db, cand), decisions=list(DECISIONS))


@router.get("/{cand_id}")
def scorecard(request: Request, cand_id: int, user: User = Depends(STAFF), db: Session = Depends(get_db)):
    return _show(request, cand_id, user, db)


@alias.get("/candidates/{cand_id}/scorecard")
def scorecard_under_candidate(request: Request, cand_id: int, user: User = Depends(STAFF), db: Session = Depends(get_db)):
    return _show(request, cand_id, user, db)


@router.post("/{cand_id}/decide")
def make_decision(request: Request, cand_id: int, decision: str = Form(""), reason: str = Form(""), user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    cand = db.get(Candidate, cand_id)
    if cand is None:
        raise HTTPException(404, "That candidate does not exist")
    try:
        decide(db, cand, decision, reason, user.email)
    except (MoveRefused, ValueError) as e:
        db.rollback()
        flash(request, f"Not recorded: {e}", "bad")
    else:
        db.commit()
        flash(request, "Your decision and reason were recorded. The email to the candidate is waiting in the outbox for your approval.")
    return RedirectResponse(f"/scorecard/{cand_id}", status_code=303)
