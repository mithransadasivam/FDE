"""The compliance page: findings from the compliance reviewer, for the recruiter to read and act on."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.compliance import open_findings, review
from app.agents.screening import rescore_candidate
from app.auth import RECRUITER, STAFF
from app.db import get_db
from app.models import DecisionLog, User
from app.models_ext import ComplianceFinding
from app.web.common import flash, render

router = APIRouter(prefix="/compliance")


@router.get("")
def compliance(request: Request, user: User = Depends(STAFF), db: Session = Depends(get_db)):
    resolved = db.scalars(select(ComplianceFinding).where(ComplianceFinding.status == "RESOLVED").order_by(ComplianceFinding.id.desc()).limit(20)).all()
    return render(request, "compliance.html", user, findings=open_findings(db), resolved=resolved)


@router.post("/run")
def run(request: Request, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    new = review(db)
    flash(request, f"Compliance review finished: {len(new)} new finding(s)." if new else "Compliance review finished: nothing new found.", "bad" if new else "good")
    return RedirectResponse("/compliance", status_code=303)


@router.post("/{finding_id}/rescore")
def rescore(request: Request, finding_id: int, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    f = db.get(ComplianceFinding, finding_id)
    if f is None or f.candidate_id is None:
        raise HTTPException(404, "That finding has no candidate to score again")
    rescore_candidate(db, f.candidate_id)
    review(db)
    flash(request, f"Candidate #{f.candidate_id} was scored again and checked.")
    return RedirectResponse("/compliance", status_code=303)


@router.post("/{finding_id}/resolve")
def resolve(request: Request, finding_id: int, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    f = db.get(ComplianceFinding, finding_id)
    if f is None:
        raise HTTPException(404, "That finding does not exist")
    f.status = "RESOLVED"
    db.add(DecisionLog(actor=user.email, action="compliance finding resolved", subject=f"finding:{f.id}", reason=f"{f.check}: {f.detail[:150]}"))
    db.commit()
    flash(request, "Finding marked as resolved (logged).")
    return RedirectResponse("/compliance", status_code=303)
