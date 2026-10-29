"""The read-only REST API (blind), its keys and webhooks, and candidates' data requests."""
import json
import secrets

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import integrations
from app.auth import HM, RECRUITER
from app.datarights import erase, export_data, open_delete_request, refuse
from app.db import get_db
from app.models import Candidate, DecisionLog, Requisition, User
from app.models_ext import ApiKey, DataRequest, InterviewSession, ItemScoreRow, Webhook, WebhookDelivery
from app.privacy import make_blind
from app.supervisor import MoveRefused
from app.web.common import flash, render

router = APIRouter()  # candidates' data rights: always on
api_router = APIRouter()  # the REST API, keys and webhooks: only mounted when ENABLE_INTEGRATIONS=1 (off by default)


# ---- the REST API --------------------------------------------------------------------------------------------------------------------------------
def api_key(request: Request, db: Session = Depends(get_db)) -> ApiKey:
    presented = request.headers.get("x-api-key") or (request.headers.get("authorization", "")[7:] if request.headers.get("authorization", "").lower().startswith("bearer ") else None)
    key = integrations.find_key(db, presented)
    if key is None:
        raise HTTPException(401, "A valid API key is needed: send it as 'Authorization: Bearer <key>' or 'X-API-Key'.")
    if integrations.over_limit(key.id):
        raise HTTPException(429, f"Rate limit: {integrations.RATE_LIMIT} requests per minute per key.")
    from datetime import datetime, timezone

    key.last_used_at = datetime.now(timezone.utc)
    db.commit()
    return key


def _scores(db: Session, req_id: int, cid: int) -> list[ItemScoreRow]:
    return list(db.scalars(select(ItemScoreRow).where(ItemScoreRow.candidate_id == cid, ItemScoreRow.requisition_id == req_id).order_by(ItemScoreRow.id)))


def _total(rows: list[ItemScoreRow]) -> float | None:
    return round(sum(r.weight * r.score for r in rows) / 3, 1) if rows else None


@api_router.get("/api/v1/health")
def api_health(_: ApiKey = Depends(api_key)):
    return {"status": "ok", "api": "v1", "read_only": True, "blind": True}


@api_router.get("/api/v1/requisitions")
def api_requisitions(_: ApiKey = Depends(api_key), db: Session = Depends(get_db)):
    return [{"id": r.id, "title": r.title, "status": r.status, "skills": [{"skill": i["skill"], "weight": i["weight"], "must_have": i["must_have"]} for i in (r.rubric or {}).get("items", [])]}
            for r in db.scalars(select(Requisition).order_by(Requisition.id))]


@api_router.get("/api/v1/requisitions/{req_id}/candidates")
def api_candidates(req_id: int, stage: str = "", _: ApiKey = Depends(api_key), db: Session = Depends(get_db)):
    if db.get(Requisition, req_id) is None:
        raise HTTPException(404, "That requisition does not exist")
    q = select(Candidate).where(Candidate.requisition_id == req_id).order_by(Candidate.id)
    if stage:
        q = q.where(Candidate.stage == stage)
    return [{"candidate": c.id, "stage": c.stage, "cv_total_100": _total(_scores(db, req_id, c.id))} for c in db.scalars(q)]


@api_router.get("/api/v1/candidates/{cand_id}")
def api_candidate(cand_id: int, _: ApiKey = Depends(api_key), db: Session = Depends(get_db)):
    from app.interview.scorecard import build_card

    c = db.get(Candidate, cand_id)
    if c is None:
        raise HTTPException(404, "That candidate does not exist")
    b = make_blind(c) if c.profile else None
    rows = _scores(db, c.requisition_id, c.id)
    s = db.query(InterviewSession).filter_by(candidate_id=c.id).first()
    card = build_card(db, s) if s and s.status == "DONE" and s.scorecard else None
    return {"candidate": c.id, "requisition": c.requisition_id, "stage": c.stage, "erased": bool(c.erased_at),
            "blind_profile": b.model_dump() if b else None,
            "cv_scores": [{"skill": r.skill, "weight": r.weight, "score": r.score, "quote": r.quote} for r in rows], "cv_total_100": _total(rows),
            "ai_interview": {"overall_100": card["overall_100"], "levels": {r["skill"]: r["level"] for r in card["skills"] if r["asked"]},
                             "scorers_disagree": card["scorers_disagree"], "reviewed_by_a_person": bool(s.reviewed_by)} if card else None}


@api_router.get("/api/v1/events")
def api_events(after: int = 0, limit: int = 100, _: ApiKey = Depends(api_key), db: Session = Depends(get_db)):
    """The decision log as an event feed (for polling): who did what, when, and why. Evidence is not included."""
    rows = db.scalars(select(DecisionLog).where(DecisionLog.id > after).order_by(DecisionLog.id).limit(min(limit, 500))).all()
    return [{"id": e.id, "at": e.at.isoformat() if e.at else None, "actor": e.actor if "@" not in e.actor else "staff", "action": e.action, "subject": e.subject, "reason": e.reason}
            for e in rows]


# ---- the integrations page (hiring manager) ---------------------------------------------------------------------------------------------------------
@api_router.get("/integrations")
def integrations_page(request: Request, user: User = Depends(HM), db: Session = Depends(get_db)):
    return render(request, "integrations.html", user, keys=db.scalars(select(ApiKey).order_by(ApiKey.id)).all(), hooks=db.scalars(select(Webhook).order_by(Webhook.id)).all(),
                  deliveries=db.scalars(select(WebhookDelivery).order_by(WebhookDelivery.id.desc()).limit(15)).all(), events=integrations.EVENTS,
                  new_key=request.session.pop("_new_key", None), live=__import__("app.config", fromlist=["get_settings"]).get_settings().webhooks_live)


@api_router.post("/integrations/keys")
def make_key(request: Request, name: str = Form(""), user: User = Depends(HM), db: Session = Depends(get_db)):
    row, key = integrations.create_key(db, name, user.email)
    db.add(DecisionLog(actor=user.email, action="API key created", subject=f"api_key:{row.id}", reason=row.name))
    db.commit()
    request.session["_new_key"] = key  # shown once
    return RedirectResponse("/integrations", status_code=303)


@api_router.post("/integrations/keys/{key_id}/revoke")
def revoke_key(request: Request, key_id: int, user: User = Depends(HM), db: Session = Depends(get_db)):
    row = db.get(ApiKey, key_id)
    if row is None:
        raise HTTPException(404, "That key does not exist")
    row.revoked = True
    db.add(DecisionLog(actor=user.email, action="API key revoked", subject=f"api_key:{row.id}", reason=row.name))
    db.commit()
    flash(request, f"Key {row.prefix}… revoked.")
    return RedirectResponse("/integrations", status_code=303)


@api_router.post("/integrations/webhooks")
async def add_webhook(request: Request, user: User = Depends(HM), db: Session = Depends(get_db)):
    form = await request.form()
    url = str(form.get("url", "")).strip()
    chosen = [v for k, v in form.multi_items() if k == "event" and v in integrations.EVENTS]
    if not url.startswith(("https://", "http://")) or not chosen:
        flash(request, "Enter a URL that starts with https:// (or http:// for a test) and choose at least one event.", "bad")
        return RedirectResponse("/integrations", status_code=303)
    hook = Webhook(url=url, events=chosen, secret=secrets.token_hex(16), created_by=user.email)
    db.add(hook)
    db.add(DecisionLog(actor=user.email, action="webhook added", subject=f"webhook:{url}", reason=", ".join(chosen)))
    db.commit()
    flash(request, f"Webhook added. Signing secret (shown once): {hook.secret}")
    return RedirectResponse("/integrations", status_code=303)


@api_router.post("/integrations/webhooks/{hook_id}/delete")
def delete_webhook(request: Request, hook_id: int, user: User = Depends(HM), db: Session = Depends(get_db)):
    hook = db.get(Webhook, hook_id)
    if hook is None:
        raise HTTPException(404, "That webhook does not exist")
    hook.active = False
    db.add(DecisionLog(actor=user.email, action="webhook removed", subject=f"webhook:{hook.url}", reason="switched off"))
    db.commit()
    return RedirectResponse("/integrations", status_code=303)


@api_router.post("/integrations/test")
def test_event(request: Request, user: User = Depends(HM), db: Session = Depends(get_db)):
    n = integrations.emit(db, "test", {"message": "a test event from the Integrations page"})
    db.commit()
    flash(request, f"Test event recorded for {n} webhook(s). See the delivery log below.")
    return RedirectResponse("/integrations", status_code=303)


# ---- candidates' data rights -------------------------------------------------------------------------------------------------------------------------
def _cand(db: Session, token: str) -> Candidate:
    c = db.scalar(select(Candidate).where(Candidate.access_token == token))
    if c is None:
        raise HTTPException(404, "We could not find that application")
    return c


@router.get("/me/{token}/data.json")
def my_data(token: str, db: Session = Depends(get_db)):
    """The candidate downloads a copy of everything we hold about them."""
    cand = _cand(db, token)
    if cand.erased_at:
        raise HTTPException(410, "Your personal data has been erased, so there is nothing to download.")
    db.add(DecisionLog(actor="candidate", action="data copy downloaded", subject=f"candidate:{cand.id}", reason="the candidate downloaded the data we hold about them"))
    db.commit()
    return Response(json.dumps(export_data(db, cand), indent=1), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="my-data-candidate-{cand.id}.json"'})


@router.post("/me/{token}/delete-request")
def ask_to_delete(token: str, db: Session = Depends(get_db)):
    cand = _cand(db, token)
    try:
        open_delete_request(db, cand)
    except MoveRefused:
        return RedirectResponse(f"/me/{token}", status_code=303)
    db.commit()
    return RedirectResponse(f"/me/{token}?data=requested", status_code=303)


@router.get("/data-requests")
def data_requests(request: Request, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    rows = db.scalars(select(DataRequest).where(DataRequest.kind == "delete").order_by(DataRequest.id.desc())).all()
    return render(request, "data_requests.html", user, rows=rows)


@router.post("/data-requests/{req_id}/decide")
def decide_request(request: Request, req_id: int, decision: str = Form(""), reason: str = Form(""), user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    req = db.get(DataRequest, req_id)
    if req is None:
        raise HTTPException(404, "That request does not exist")
    cand = db.get(Candidate, req.candidate_id)
    try:
        if req.status != "REQUESTED":
            raise MoveRefused("That request has already been decided.")
        if decision == "approve":
            erase(db, cand, req, user.email, reason)
        elif decision == "refuse":
            refuse(db, cand, req, user.email, reason)
        else:
            raise MoveRefused("Choose Approve erasure or Refuse.")
    except MoveRefused as e:
        db.rollback()
        flash(request, f"Not recorded: {e}", "bad")
    else:
        db.commit()
        flash(request, "Personal data erased. The decision log keeps who decided and why." if decision == "approve" else "Refused. The reason is on record.")
    return RedirectResponse("/data-requests", status_code=303)
