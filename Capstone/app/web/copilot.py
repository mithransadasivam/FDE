"""The interview copilot panel (recruiter only): replays a recorded interview as if live and streams what the copilot sees."""
import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.copilot import CopilotAgent
from app.auth import RECRUITER
from app.config import get_settings
from app.db import SessionLocal, get_db
from app.models import Candidate, DecisionLog, Requisition, User
from app.models_ext import HumanInterview, InterviewSession
from app.schemas import Stage
from app.supervisor import MoveRefused, move
from app.voice.replayer import get_interview, load_interviews, replay
from app.web.common import flash, render

router = APIRouter(prefix="/copilot")

COPILOT_NOTICE = ("This interview will be followed by an AI assistant that listens, shows the recruiter a live transcript, suggests questions and "
                  "ticks the points of a good answer. It never decides: the recruiter asks, scores and decides. The conversation is recorded and kept for "
                  "6 months. You can ask for the interview to be held without the assistant.")


def _cand(db: Session, cand_id: int) -> Candidate:
    c = db.get(Candidate, cand_id)
    if c is None:
        raise HTTPException(404, "That candidate does not exist")
    return c


def _hi(db: Session, cand_id: int) -> HumanInterview | None:
    return db.scalars(select(HumanInterview).where(HumanInterview.candidate_id == cand_id).order_by(HumanInterview.id.desc())).first()


def recording_for(cand: Candidate) -> dict | None:
    """The interview the copilot follows: a practice interview made for this candidate (scripts/make_recruiter_interview.py) if there is one, otherwise the recorded
    interview from the starter kit."""
    from app.practice import load_practice

    practice = load_practice(cand.id)
    if practice:
        return {**practice, "kind": "practice interview (SAMPLE: fictional)", "storage": True}
    return next((i for i in load_interviews() if i["cv_file"] == cand.cv_name), None)


@router.get("")
def copilot_home(request: Request, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    rows = []
    for c in db.scalars(select(Candidate).where(Candidate.stage.in_(["SHORTLISTED", "AI_INTERVIEW", "HUMAN_INTERVIEW", "DECISION"])).order_by(Candidate.id)):
        rows.append({"c": c, "rec": recording_for(c), "hi": _hi(db, c.id)})
    return render(request, "copilot_home.html", user, rows=rows)


@router.get("/{cand_id}")
def copilot_panel(request: Request, cand_id: int, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    cand = _cand(db, cand_id)
    from app.interview.bank import load_questions
    from app.models_ext import HumanInterviewScore

    rows = db.scalars(select(HumanInterviewScore).where(HumanInterviewScore.candidate_id == cand_id)).all()
    return render(request, "copilot.html", user, cand=cand, rec=recording_for(cand), hi=_hi(db, cand_id), notice=COPILOT_NOTICE, qs=load_questions(),
                  saved={r.question_id: r.level for r in rows}, reasons={r.question_id: r.reason for r in rows})


@router.post("/{cand_id}/to-human-interview")
def to_human_interview(request: Request, cand_id: int, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    cand = _cand(db, cand_id)
    session = db.query(InterviewSession).filter_by(candidate_id=cand.id).first()
    asked = bool(session and session.status == "PERSON_REQUESTED")
    try:
        move(db, cand, Stage.HUMAN_INTERVIEW, user.email, "interview with a person, as the candidate asked" if asked else "second-round interview with a recruiter",
             evidence={"asked_for_person": True} if asked else None)
        from app.agents.communications import draft_invitation
        draft_invitation(db, cand, kind="invitation")
    except MoveRefused as e:
        db.rollback()
        flash(request, f"Refused: {e}", "bad")
    else:
        db.commit()
        flash(request, "Moved to HUMAN_INTERVIEW. An invitation with a proposed slot is waiting in the outbox for your approval.")
    return RedirectResponse(f"/copilot/{cand_id}", status_code=303)


@router.post("/{cand_id}/ack")
def acknowledge(request: Request, cand_id: int, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    """The recruiter confirms the candidate was told AI assists and did not ask for the interview without it (rule 5)."""
    cand = _cand(db, cand_id)
    rec = recording_for(cand)
    hi = _hi(db, cand_id) or HumanInterview(candidate_id=cand_id, recording=rec["file"] if rec else "")
    hi.notice_ack, hi.status = True, "READY"
    db.add(hi)
    db.add(DecisionLog(actor=user.email, action="copilot notice confirmed", subject=f"candidate:{cand_id}", reason="candidate told an AI assistant follows the interview and agreed"))
    db.commit()
    flash(request, "Confirmed. The copilot can follow this interview.")
    return RedirectResponse(f"/copilot/{cand_id}", status_code=303)


@router.post("/{cand_id}/decline")
def decline(request: Request, cand_id: int, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    """The candidate asked for the interview without the assistant: the copilot is not started."""
    hi = _hi(db, cand_id) or HumanInterview(candidate_id=cand_id)
    hi.status, hi.notice_ack = "NO_COPILOT", False
    db.add(hi)
    db.add(DecisionLog(actor=user.email, action="candidate declined the copilot", subject=f"candidate:{cand_id}", reason="interview held without the AI assistant"))
    db.commit()
    flash(request, "Noted: the interview will be held without the assistant.")
    return RedirectResponse(f"/copilot/{cand_id}", status_code=303)


@router.get("/{cand_id}/events")
def events(cand_id: int, speed: float = 8.0, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    """Server-sent events: the copilot following the recorded interview (speed = replay seconds per real second; 0 = instant)."""
    cand = _cand(db, cand_id)
    rec = recording_for(cand)
    hi = _hi(db, cand_id)
    if rec is None or hi is None or not hi.notice_ack:
        raise HTTPException(403, "The candidate must be told about the AI assistant, and the recruiter must confirm it, before the copilot starts")
    req_id, hi_id = cand.requisition_id, hi.id

    def gen():
        with SessionLocal() as s:
            c, req = s.get(Candidate, cand_id), s.get(Requisition, req_id)
            agent = CopilotAgent(s, c, req)
            for turn in replay(rec, max(0.0, speed)):
                for e in agent.process_turn(turn["speaker"], turn["text"], turn["start"], turn["end"]):
                    yield f"event: copilot\ndata: {json.dumps(e.model_dump())}\n\n"
            draft = agent.draft_scorecard()
            row = s.get(HumanInterview, hi_id)
            row.events, row.draft_scorecard, row.status = [e.model_dump() for e in agent.events], draft, "DONE"
            row.source, row.started_at = "practice" if rec.get("storage") else "recording", datetime.now(timezone.utc)
            row.lines = [{"speaker": e.data["speaker"], "text": e.data["text"], "start": e.data["start"], "end": e.data["end"]} for e in agent.events if e.kind == "transcript"]
            s.add(DecisionLog(actor="system", action="copilot followed interview", subject=f"candidate:{cand_id}",
                              reason=f"{len(agent.warnings)} warning(s), {len(agent.conflicts)} CV check(s); draft scorecard saved for the recruiter"))
            s.commit()
            yield f"event: draft\ndata: {json.dumps(draft)}\n\n"
            yield "event: end\ndata: {}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/{cand_id}/scores")
async def recruiter_scores(request: Request, cand_id: int, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    """The recruiter scores the human interview on the SAME 0-3 scale as the AI interview. The copilot's suggestion is shown, labelled, but the person's level is what is
    saved; when the two differ by 2 or more a short reason is required."""
    from app.models_ext import HumanInterviewScore

    hi = _hi(db, cand_id)
    if hi is None or hi.status != "DONE":
        flash(request, "Let the copilot follow the interview first.", "bad")
        return RedirectResponse(f"/copilot/{cand_id}", status_code=303)
    form = await request.form()
    suggestions = {a["question_id"]: a for a in (hi.draft_scorecard or {}).get("answers", []) if a.get("type") == "technical"}
    saved, problems = [], []
    for qid, a in suggestions.items():
        raw = str(form.get(f"score_{qid}", "")).strip()
        if raw == "":
            continue
        if not raw.isdigit() or not 0 <= int(raw) <= 3:
            problems.append(f"{a['skill']}: enter a level from 0 to 3.")
            continue
        level, ai = int(raw), a.get("suggested_score")
        reason = str(form.get(f"reason_{qid}", "")).strip()
        if ai is not None and abs(level - ai) >= 2 and not reason:
            problems.append(f"{a['skill']}: your level ({level}) is {abs(level - ai)} away from the AI suggestion ({ai}); write a short reason.")
            continue
        saved.append(HumanInterviewScore(candidate_id=cand_id, question_id=qid, skill=a["skill"], level=level, ai_suggestion=ai, ai_quote=a.get("quote", ""), reason=reason, scored_by=user.email))
    if problems:
        db.rollback()
        flash(request, "Not saved. " + " ".join(problems), "bad")
        return RedirectResponse(f"/copilot/{cand_id}", status_code=303)
    if not saved:
        flash(request, "Enter at least one level.", "bad")
        return RedirectResponse(f"/copilot/{cand_id}", status_code=303)
    for old in db.scalars(select(HumanInterviewScore).where(HumanInterviewScore.candidate_id == cand_id)):
        db.delete(old)  # saving again replaces the earlier scores
    for row in saved:
        db.add(row)
    scores = {r.question_id: r.level for r in saved}
    hi.recruiter_scores = {"scores": scores, "by": user.email, "note": str(form.get("note", ""))}
    db.add(DecisionLog(actor=user.email, action="human interview scored", subject=f"candidate:{cand_id}", reason=str(form.get("note", ""))[:200] or f"{len(saved)} skill(s) scored by the recruiter",
                       evidence={"recruiter_levels": scores, "ai_suggestions": {q: a.get("suggested_score") for q, a in suggestions.items()}, "copilot_draft": hi.draft_scorecard}))
    db.commit()
    flash(request, "Your levels were saved. They are the scores; the copilot's suggestions stay beside them, labelled.")
    return RedirectResponse(f"/copilot/{cand_id}", status_code=303)


@router.post("/{cand_id}/decide")
def decide_human(request: Request, cand_id: int, decision: str = Form(""), reason: str = Form(""), user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    """After scoring: "Recommend for offer stage" (HUMAN_INTERVIEW -> DECISION) or "Withdraw", through supervisor.move with the recruiter as actor and a required reason.
    The evidence checker's problems must have been looked at first."""
    from app.decisions import decide
    from app.models_ext import HumanInterviewScore

    cand = _cand(db, cand_id)
    try:
        if not db.scalars(select(HumanInterviewScore).where(HumanInterviewScore.candidate_id == cand_id)).first():
            raise MoveRefused("Score the interview yourself first: the decision comes after your own levels.")
        if decision == "offer":
            decide(db, cand, "OFFER_RECOMMENDED", reason, user.email)
        elif decision == "withdraw":
            move(db, cand, Stage.WITHDRAWN, user.email, reason, evidence={"human_interview": "withdrawn after the human interview"})
        else:
            raise MoveRefused("Choose Recommend for offer stage, or Withdraw.")
    except (MoveRefused, ValueError) as e:  # a ValueError here is a missing or too-short reason
        db.rollback()
        flash(request, f"Not recorded: {e if isinstance(e, MoveRefused) else 'a decision needs a reason'}", "bad")
    else:
        db.commit()
        flash(request, "Your decision and reason are in the decision log." + (" An email draft waits in the outbox for your approval." if decision == "offer" else ""))
    return RedirectResponse(f"/copilot/{cand_id}", status_code=303)


@router.get("/{cand_id}/audio")
def audio(cand_id: int, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    rec = recording_for(_cand(db, cand_id))
    p = (get_settings().storage_dir / rec["file"] if rec.get("storage") else Path(get_settings().kit_dir) / rec["file"]) if rec else None
    if p is None or not p.exists():
        raise HTTPException(404, "No recording")
    return FileResponse(p, media_type="audio/wav")


# ---- live microphone: the recruiter's browser sends the interview in short pieces; two buttons say who is speaking --------------------------------------------
LIVE: dict[int, dict] = {}  # candidate id -> {"agent", "db", "clock"}: one running live session per candidate


def _live(db: Session, cand: Candidate, hi: HumanInterview | None) -> dict:
    if hi is None or not hi.notice_ack:
        raise HTTPException(403, "The candidate must be told about the AI assistant, and the recruiter must confirm it, before the copilot starts")
    if cand.id not in LIVE:
        sess = SessionLocal()
        c = sess.get(Candidate, cand.id)
        LIVE[cand.id] = {"agent": CopilotAgent(sess, c, sess.get(Requisition, c.requisition_id)), "db": sess, "clock": 0.0, "lines": []}
        hi.source, hi.started_at, hi.status = "live", datetime.now(timezone.utc), "LIVE"
        db.commit()
    return LIVE[cand.id]


@router.post("/{cand_id}/live/line")
async def live_line(cand_id: int, speaker: str = Form(...), text: str = Form(""), audio_file: UploadFile | None = File(None, alias="audio"),
                    user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    """One piece of the live interview. The speaker comes from the button the recruiter pressed (Recruiter speaking / Candidate speaking). Audio is transcribed with
    app/ai/voice.py (in fake mode only recorded fixtures can be, so a typed line is accepted too). The line goes through the same copilot as a recording."""
    from app.ai import audio as audio_tools, voice

    if speaker not in ("recruiter", "candidate"):
        raise HTTPException(400, "The speaker must be recruiter or candidate")
    cand = _cand(db, cand_id)
    live = _live(db, cand, _hi(db, cand_id))
    seconds = None
    if not text.strip() and audio_file is not None and audio_file.filename:
        data = await audio_file.read()
        if not data or len(data) > 25 * 1024 * 1024:
            raise HTTPException(400, "The recording piece is empty or too large")
        folder = get_settings().storage_dir / "copilot" / str(cand_id)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"piece_{len(live['lines']) + 1:03d}{Path(audio_file.filename).suffix.lower() or '.webm'}"
        path.write_bytes(data)
        try:
            src = audio_tools.to_wav(path, path.with_suffix(".wav")) if path.suffix != ".wav" else path
            text, seconds = voice.transcribe(src, path.name), voice.audio_duration(src)
        except FileNotFoundError:
            raise HTTPException(422, "Fake mode cannot transcribe a new recording: type the line instead") from None
        except audio_tools.AudioError as e:
            raise HTTPException(422, f"{e} Please try again or type the line.") from e
        finally:
            path.unlink(missing_ok=True)
            path.with_suffix(".wav").unlink(missing_ok=True)
    text = text.strip()
    if not text:
        raise HTTPException(400, "There is nothing to add: no speech was heard")
    start = live["clock"]
    end = start + (seconds if seconds else max(1.0, voice.speaking_seconds(text)))
    live["clock"] = end + 0.3
    events = live["agent"].process_turn(speaker, text, start, end)
    live["lines"].append({"speaker": speaker, "text": text, "start": round(start, 2), "end": round(end, 2)})
    hi = _hi(db, cand_id)
    hi.lines, hi.events = live["lines"], [e.model_dump() for e in live["agent"].events]  # every line is saved to the session as it arrives
    db.commit()
    return {"events": [e.model_dump() for e in events]}


@router.post("/{cand_id}/live/asked")
def live_asked(cand_id: int, question_id: str = Form(...), user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    """"I asked this": tells the copilot which question the next answer is about."""
    live = LIVE.get(cand_id)
    if live is None:
        raise HTTPException(409, "There is no live session running")
    live["agent"].asked(question_id)
    return {"ok": True, "active": question_id}


@router.post("/{cand_id}/live/end")
def live_end(cand_id: int, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    live = LIVE.pop(cand_id, None)
    hi = _hi(db, cand_id)
    if live is None or hi is None:
        raise HTTPException(409, "There is no live session running")
    agent = live["agent"]
    draft = agent.draft_scorecard()
    hi.events, hi.draft_scorecard, hi.status = [e.model_dump() for e in agent.events], draft, "DONE"
    db.add(DecisionLog(actor="system", action="copilot followed interview", subject=f"candidate:{cand_id}",
                       reason=f"live: {len(agent.warnings)} warning(s), {len(agent.conflicts)} CV check(s); draft scorecard saved for the recruiter"))
    db.commit()
    live["db"].close()
    return {"draft": draft}
