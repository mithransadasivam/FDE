"""Insight pages for buyers and teams: analytics, side-by-side comparison (blind), and exports (CSV, a PDF scorecard, an audit bundle).

Everything shown about a candidate here is the BLIND view (a number, scores, quotes), never a name or contact detail (rule 3).
"""
import csv
import hashlib
import io
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import analytics
from app.auth import AUDIT, INSIGHT, STAFF
from app.db import get_db
from app.decisions import build_scorecard
from app.models import Candidate, DecisionLog, Requisition, User
from app.models_ext import ComplianceFinding, InterviewSession, ItemScoreRow, OutboxLog
from app.web.common import render

router = APIRouter()


# ---- analytics -----------------------------------------------------------------------------------------------------------------------
@router.get("/analytics")
def analytics_page(request: Request, req: int | None = None, user: User = Depends(INSIGHT), db: Session = Depends(get_db)):
    data = analytics.everything(db, req)
    top = max((r["n"] for r in data["funnel"]), default=1) or 1
    peak = max((b["n"] for b in data["scores"]), default=1) or 1
    return render(request, "analytics.html", user, **data, top=top, peak=peak)


# ---- comparison ------------------------------------------------------------------------------------------------------------------------
MAX_COMPARE = 5


def comparison(db: Session, req_id: int, ids: list[int]) -> dict:
    """The chosen candidates side by side: every rubric skill's CV score with its quote, the total, and the AI interview's overall score."""
    from app.interview.scorecard import build_card

    req = db.get(Requisition, req_id)
    if req is None:
        raise HTTPException(404, "That requisition does not exist")
    skills = [i["skill"] for i in (req.rubric or {}).get("items", [])]
    cols = []
    for cid in ids[:MAX_COMPARE]:
        cand = db.get(Candidate, cid)
        if cand is None or cand.requisition_id != req_id:
            continue
        rows = {r.skill: r for r in db.scalars(select(ItemScoreRow).where(ItemScoreRow.candidate_id == cid, ItemScoreRow.requisition_id == req_id))}
        s = db.query(InterviewSession).filter_by(candidate_id=cid).first()
        card = build_card(db, s) if s and s.status == "DONE" and s.scorecard else None
        total = round(sum(r.weight * r.score for r in rows.values()) / 3, 1) if rows else None
        cols.append({"id": cid, "stage": cand.stage, "total": total, "scores": rows, "interview": card["overall_100"] if card else None,
                     "interview_levels": {r["skill"]: r["level"] for r in card["skills"] if r["asked"]} if card else {}})
    best = {sk: max((c["scores"][sk].score for c in cols if sk in c["scores"]), default=None) for sk in skills}
    return {"req": req, "skills": skills, "cols": cols, "best": best}


@router.get("/compare")
def compare_page(request: Request, req: int | None = None, ids: str = "", user: User = Depends(STAFF), db: Session = Depends(get_db)):
    reqs = db.scalars(select(Requisition).where(Requisition.status.in_(["APPROVED", "PUBLISHED"])).order_by(Requisition.id)).all()
    if not reqs:
        raise HTTPException(404, "There is no approved job yet")
    req_id = req or reqs[0].id
    chosen = [int(x) for x in ids.split(",") if x.strip().isdigit()]
    pool = db.scalars(select(Candidate).where(Candidate.requisition_id == req_id, Candidate.stage.in_(["SCREENED", "SHORTLISTED", "AI_INTERVIEW", "HUMAN_INTERVIEW", "DECISION"]))
                      .order_by(Candidate.id)).all()
    data = comparison(db, req_id, chosen) if chosen else None
    return render(request, "compare.html", user, reqs=reqs, req_id=req_id, pool=pool, chosen=chosen, data=data, max_compare=MAX_COMPARE)


# ---- exports -----------------------------------------------------------------------------------------------------------------------------------
def _csv(rows: list[list], name: str) -> Response:
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/export/candidates.csv")
def export_candidates(req: int, user: User = Depends(STAFF), db: Session = Depends(get_db)):
    """One row per candidate, blind: a number, the stage, the CV total, each skill's score and the AI interview's overall score. No names or contact details."""
    from app.interview.scorecard import build_card

    job = db.get(Requisition, req)
    if job is None:
        raise HTTPException(404, "That requisition does not exist")
    skills = [i["skill"] for i in (job.rubric or {}).get("items", [])]
    rows = [["candidate", "stage", "cv_total_100", *skills, "ai_interview_overall_100"]]
    for c in db.scalars(select(Candidate).where(Candidate.requisition_id == req).order_by(Candidate.id)):
        sc = {r.skill: r.score for r in db.scalars(select(ItemScoreRow).where(ItemScoreRow.candidate_id == c.id, ItemScoreRow.requisition_id == req))}
        s = db.query(InterviewSession).filter_by(candidate_id=c.id).first()
        ai = build_card(db, s)["overall_100"] if s and s.status == "DONE" and s.scorecard else ""
        total = round(sum(i["weight"] * sc.get(i["skill"], 0) for i in (job.rubric or {}).get("items", [])) / 3, 1) if sc else ""
        rows.append([c.id, c.stage, total, *[sc.get(k, "") for k in skills], ai])
    return _csv(rows, f"candidates-req-{req}.csv")


@router.get("/export/decision-log.csv")
def export_log(user: User = Depends(INSIGHT), db: Session = Depends(get_db)):
    rows = [["id", "at", "actor", "action", "subject", "reason"]]
    for e in db.scalars(select(DecisionLog).order_by(DecisionLog.id)):
        rows.append([e.id, e.at.isoformat() if e.at else "", e.actor, e.action, e.subject, e.reason])
    return _csv(rows, "decision-log.csv")


@router.get("/export/audit.json")
def export_audit(user: User = Depends(AUDIT), db: Session = Depends(get_db)):
    """The audit bundle for a compliance review: decision log, outbox and compliance findings, with a SHA-256 of the content so a change is visible."""
    body = {"exported_at": datetime.now(timezone.utc).isoformat(), "exported_by": user.email,
            "decision_log": [{"id": e.id, "at": e.at.isoformat() if e.at else None, "actor": e.actor, "action": e.action, "subject": e.subject, "reason": e.reason}
                             for e in db.scalars(select(DecisionLog).order_by(DecisionLog.id))],
            "outbox": [{"id": o.id, "at": o.at.isoformat() if o.at else None, "to_candidate": o.to_candidate, "approved_by": o.approved_by, "subject": o.subject}
                       for o in db.scalars(select(OutboxLog))],
            "compliance_findings": [{"id": f.id, "check": f.check, "severity": f.severity, "status": f.status, "detail": f.detail}
                                    for f in db.scalars(select(ComplianceFinding))]}
    digest = hashlib.sha256(json.dumps({k: v for k, v in body.items() if k not in ("exported_at", "exported_by")}, sort_keys=True).encode()).hexdigest()
    db.add(DecisionLog(actor=user.email, action="audit bundle exported", subject="system", reason=f"{len(body['decision_log'])} log entries, sha256 {digest[:12]}"))
    db.commit()
    return JSONResponse({**body, "sha256": digest}, headers={"Content-Disposition": 'attachment; filename="audit-bundle.json"'})


@router.get("/export/scorecard/{cand_id}.pdf")
def export_scorecard_pdf(cand_id: int, user: User = Depends(STAFF), db: Session = Depends(get_db)):
    """A one-page PDF of a candidate's scorecard for sharing with a hiring panel: blind, with the evidence behind every number."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    cand = db.get(Candidate, cand_id)
    if cand is None:
        raise HTTPException(404, "That candidate does not exist")
    card = build_scorecard(db, cand)
    st = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title=f"Scorecard candidate {cand_id}", leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
    story = [Paragraph(f"Scorecard &middot; candidate #{cand_id}", st["Title"]),
             Paragraph(f"{card['job']} &middot; stage {card['stage']} &middot; blind view: no name or contact details", st["Normal"]), Spacer(1, 10)]
    if card["cv_scores"]:
        rows = [["Skill", "Weight", "Score", "Quote from the CV"]] + [[r["skill"], r["weight"], f"{r['score']}/3", (f"“{r['quote']}”" if r["quote"] else "")[:70]] for r in card["cv_scores"]]
        t = Table(rows, colWidths=[150, 45, 45, 270])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f46e5")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("FONTSIZE", (0, 0), (-1, -1), 8),
                               ("GRID", (0, 0), (-1, -1), 0.25, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        story += [Paragraph(f"CV total: <b>{card['cv_total']} / 100</b>", st["Heading3"]), t, Spacer(1, 10)]
    ai = card.get("ai_interview")
    if ai:
        story.append(Paragraph(f"AI interview: average <b>{ai.get('total')}/3</b> &middot; ended: {ai.get('ended_reason')}", st["Heading3"]))
        if (ai.get("summary") or {}).get("text"):
            story.append(Paragraph("AI-written summary: " + ai["summary"]["text"], st["Normal"]))
    story += [Spacer(1, 8), Paragraph(card["recommendation"], st["Normal"])]
    if card["decision"]:
        d = card["decision"]
        story.append(Paragraph(f"Decision by <b>{d['actor']}</b>: {d['decision']} &mdash; {d['reason']}", st["Normal"]))
    story += [Spacer(1, 14), Paragraph("The AI recommends; a person decides. Every score above has a quote that code found in the source text.", st["Italic"])]
    doc.build(story)
    db.add(DecisionLog(actor=user.email, action="scorecard PDF exported", subject=f"candidate:{cand_id}", reason=f"{user.role} downloaded the blind scorecard PDF"))
    db.commit()
    return Response(buf.getvalue(), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="scorecard-{cand_id}.pdf"'})
