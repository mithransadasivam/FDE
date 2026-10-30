"""The AI first-round interview: the candidate's page (private link, no sign-in) and the recruiter's review (Day 2)."""
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.interviewer import InterviewerAgent, get_or_create_session, request_person
from app.ai import audio, voice
from app.interview import recording
from app.interview.scorecard import build_card
from app.auth import RECRUITER, STAFF
from app.config import get_settings
from app.db import get_db
from app.interview.bank import build_plan, diagram_path, load_questions
from app.interview.replay import load_recorded, run_recorded_interview
from app.models import Candidate, DecisionLog, Requisition, User
from app.models_ext import InterviewSession
from app.privacy import make_blind
from app.supervisor import MoveRefused, move
from app.schemas import Stage
from app.web.common import flash, render

router = APIRouter()
AUDIO_TYPES = {".wav", ".mp3", ".m4a", ".webm", ".ogg"}

NOTICE = ("You are about to talk to an AI interviewer. The interview takes about 25 minutes and you answer by voice. The questions follow on "
          "from your answers, and some come with a diagram. Your answers are turned into text, and the text is scored by AI against the skills for this role. "
          "Only what you say is scored, never your voice, accent or how you speak. The interview is recorded (the questions and your answers) so the hiring "
          "team can review it: the hiring manager and the recruiters for this job can listen to it, and the recording is deleted after 6 months. "
          "A recruiter reviews every interview and makes every decision. If you would rather speak to a person, choose \"Ask for a person instead\": "
          "it will not affect how your application is treated.")
CONSENT_TEXT = "I understand the interview is recorded"


def _cand(db: Session, token: str) -> Candidate:
    c = db.scalar(select(Candidate).where(Candidate.access_token == token))
    if c is None:
        raise HTTPException(404, "We could not find that interview")
    return c


def _agent(db: Session, cand: Candidate) -> tuple[InterviewerAgent, Requisition]:
    req = db.get(Requisition, cand.requisition_id)
    return InterviewerAgent(db, get_or_create_session(db, cand)), req


# ---- the candidate's page -------------------------------------------------------------------------------------------------------
@router.get("/interview/{token}")
def interview_page(request: Request, token: str, db: Session = Depends(get_db)):
    cand = _cand(db, token)
    session = db.query(InterviewSession).filter_by(candidate_id=cand.id).first()
    invited = cand.stage == "AI_INTERVIEW"
    status = session.status if session else "NOT_STARTED"
    fixtures = [{"id": a["id"], "q": a["question_id"], "kind": a["kind"]} for a in load_recorded()] if get_settings().fake_models else []
    return render(request, "interview.html", None, cand=cand, invited=invited, status=status, notice=NOTICE, consent_text=CONSENT_TEXT, token=token,
                  title=db.get(Requisition, cand.requisition_id).title, fake=get_settings().fake_models, fixtures=fixtures,
                  acked=bool(session and session.notice_ack))


@router.post("/interview/{token}/notice")
def acknowledge_notice(token: str, agree: str = Form(""), db: Session = Depends(get_db)):
    """The candidate ticks "I understand the interview is recorded". Starting is refused until they have (checked here, not only in the page)."""
    cand = _cand(db, token)
    if cand.stage != "AI_INTERVIEW":
        raise HTTPException(403, "You have not been invited to an AI interview yet")
    if agree != "yes":
        raise HTTPException(400, "Please tick the box to say you understand the interview is recorded")
    s = get_or_create_session(db, cand)
    if not s.notice_ack:
        s.notice_ack, s.consent_recording, s.consent_at = True, True, datetime.now(timezone.utc)
        db.add(DecisionLog(actor="candidate", action="AI notice acknowledged", subject=f"candidate:{cand.id}",
                           reason="before the AI interview: the candidate agreed to the interview being recorded"))
    db.commit()
    return {"ok": True}


@router.post("/me/{token}/interview/start")
def me_start_interview(request: Request, token: str, agree: str = Form(""), db: Session = Depends(get_db)):
    """The "Start my interview" button on the candidate's own page: the tick box is required, then the interview page opens."""
    from app.web.public import me_context

    cand = _cand(db, token)
    if cand.stage != "AI_INTERVIEW":
        raise HTTPException(403, "You have not been invited to an AI interview yet")
    if agree != "yes":
        return render(request, "me.html", None, status_code=400, **{**me_context(db, cand), "interview_error": "Please tick the box to say you understand the interview is recorded."})
    acknowledge_notice(token, "yes", db)
    return RedirectResponse(f"/interview/{token}", status_code=303)


@router.post("/me/{token}/interview/person")
def me_ask_for_person(token: str, db: Session = Depends(get_db)):
    cand = _cand(db, token)
    try:
        request_person(db, cand)
    except PermissionError as e:
        raise HTTPException(409, str(e)) from e
    return RedirectResponse(f"/me/{token}", status_code=303)


@router.post("/interview/{token}/start")
def start(token: str, db: Session = Depends(get_db)):
    """Needs the consent tick. Creates the opening question (turn 1), speaks it into storage/interviews/<id>/turn_01_question.wav and returns
    the text and the audio address."""
    cand = _cand(db, token)
    if cand.stage != "AI_INTERVIEW":
        raise HTTPException(403, "You have not been invited to an AI interview yet")
    agent, req = _agent(db, cand)
    try:
        return {"prompt": agent.start(req, opening=True)}
    except PermissionError as e:
        raise HTTPException(409, str(e)) from e


@router.get("/interview/{token}/state")
def state(token: str, db: Session = Depends(get_db)):
    cand = _cand(db, token)
    agent, _ = _agent(db, cand)
    return {"status": agent.session.status, "prompt": agent.next_prompt()}


@router.get("/interview/{token}/audio/{name}")
def question_audio(token: str, name: str, db: Session = Depends(get_db)):
    """The spoken question, for the page's player. Only this candidate's own question and hint files: never their answers or anyone else's."""
    cand = _cand(db, token)
    if not re.fullmatch(r"turn_\d{2}_(?:question|hint\d+)\.wav", name):
        raise HTTPException(404, "That audio is not available")
    path = get_settings().storage_dir / "interviews" / str(get_or_create_session(db, cand).id) / name
    if not path.exists():
        raise HTTPException(404, "That audio is not available")
    return FileResponse(path, media_type="audio/wav")


def _finished(background: BackgroundTasks, agent: InterviewerAgent, result: dict) -> dict:
    """When the interview has just finished, its full recording is built in the background (the page has already replied)."""
    if result.get("done"):
        background.add_task(recording.build_recording_job, agent.session.id)
    return result


def _save_answer_audio(agent: InterviewerAgent, data: bytes, suffix: str) -> tuple[Path, str]:
    """Saves an uploaded answer as turn_NN_answer.<ext> in the interview's folder. Returns the path and the address relative to storage."""
    agent.folder.mkdir(parents=True, exist_ok=True)
    dest = agent.folder / f"turn_{agent.question_number():02d}_answer{suffix}"
    dest.write_bytes(data)
    return dest, str(dest.relative_to(get_settings().storage_dir)).replace("\\", "/")


def _heard(path: Path, original_name: str) -> tuple[str, float]:
    """Transcribes a recording. A browser's webm is converted to wav first (with a clear error if that fails)."""
    source = path
    if path.suffix.lower() != ".wav":
        try:
            source = audio.to_wav(path, path.with_suffix(".conv.wav"))
        except audio.AudioError as e:
            raise HTTPException(422, f"{e} Please record again or type your answer.") from e
    try:
        text = voice.transcribe(source, original_name or path.name)
        seconds = voice.audio_duration(source)
    except FileNotFoundError:
        raise HTTPException(422, "Fake mode cannot transcribe a new recording: type your answer in the box, or play a recorded answer") from None
    finally:
        if source != path:
            source.unlink(missing_ok=True)
    return text, seconds


async def _read_audio(audio_file: UploadFile) -> tuple[bytes, str]:
    suffix = Path(audio_file.filename or "").suffix.lower() or ".webm"
    if suffix not in AUDIO_TYPES:
        raise HTTPException(400, "That audio format is not accepted")
    data = await audio_file.read()
    if not data or len(data) > 25 * 1024 * 1024:
        raise HTTPException(400, "The recording is empty or too large")
    return data, suffix


@router.post("/interview/{token}/record")
async def record(token: str, audio_file: UploadFile = File(..., alias="audio"), db: Session = Depends(get_db)):
    """Step 1 of an answer: the recording is saved and transcribed, and the transcript is shown. Nothing is scored until the candidate presses
    Submit this answer; "Record again" deletes this recording."""
    cand = _cand(db, token)
    agent, _ = _agent(db, cand)
    if agent.session.status != "IN_PROGRESS":
        raise HTTPException(409, "The interview is not in progress")
    data, suffix = await _read_audio(audio_file)
    _discard(agent)  # a recording that was not submitted is replaced
    dest, ref = _save_answer_audio(agent, data, suffix)
    t0 = time.perf_counter()
    try:
        text, seconds = _heard(dest, audio_file.filename or "")
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise
    agent.session.state["pending"] = {"audio": ref, "text": text, "seconds": seconds, "transcription_s": round(time.perf_counter() - t0, 4)}
    agent._save()
    return {"transcript": text, "seconds": seconds}


def _discard(agent: InterviewerAgent) -> None:
    pending = (agent.session.state or {}).pop("pending", None)
    if pending:
        (get_settings().storage_dir / pending["audio"]).unlink(missing_ok=True)  # a discarded recording is deleted at once


@router.post("/interview/{token}/discard")
def discard(token: str, db: Session = Depends(get_db)):
    cand = _cand(db, token)
    agent, _ = _agent(db, cand)
    _discard(agent)
    agent._save()
    return {"ok": True}


@router.post("/interview/{token}/submit")
def submit(token: str, background: BackgroundTasks, db: Session = Depends(get_db)):
    """Step 2 of an answer: the transcript that was shown is submitted and scored; the next question follows."""
    cand = _cand(db, token)
    agent, _ = _agent(db, cand)
    pending = (agent.session.state or {}).get("pending")
    if agent.session.status != "IN_PROGRESS" or not pending:
        raise HTTPException(409, "There is no recorded answer to submit")
    agent.session.state.pop("pending")
    try:
        return _finished(background, agent, agent.submit(text=pending["text"], audio_ref=pending["audio"], duration_s=pending["seconds"] or None,
                                                         transcription_s=pending.get("transcription_s", 0.0)))
    except PermissionError as e:
        raise HTTPException(409, str(e)) from e


@router.post("/interview/{token}/answer")
async def answer(token: str, background: BackgroundTasks, audio_file: UploadFile | None = File(None, alias="audio"), text: str = Form(""),
                 fixture: str = Form(""), db: Session = Depends(get_db)):
    """Answers in one step (typed text, a recorded demo answer, or an upload that is scored at once). The browser's own flow is record, then submit."""
    cand = _cand(db, token)
    agent, _ = _agent(db, cand)
    if agent.session.status != "IN_PROGRESS":
        raise HTTPException(409, "The interview is not in progress")
    try:
        if fixture and get_settings().fake_models:  # demo mode: play one of the recorded answers
            rec = next((a for a in load_recorded() if a["id"] == fixture), None)
            if rec is None:
                raise HTTPException(400, "Unknown recorded answer")
            path = Path(get_settings().kit_dir) / rec["file"]
            return _finished(background, agent, agent.submit(audio_path=path, original_name=path.name, audio_ref=rec["file"]))
        if audio_file is not None and audio_file.filename:
            data, suffix = await _read_audio(audio_file)
            dest, ref = _save_answer_audio(agent, data, suffix)
            t0 = time.perf_counter()
            try:
                heard, seconds = _heard(dest, audio_file.filename)
            except HTTPException:
                if not text.strip():
                    dest.unlink(missing_ok=True)
                    raise
                return _finished(background, agent, agent.submit(text=text))
            return _finished(background, agent, agent.submit(text=heard, audio_ref=ref, duration_s=seconds or None, transcription_s=round(time.perf_counter() - t0, 4)))
        return _finished(background, agent, agent.submit(text=text))
    except PermissionError as e:
        raise HTTPException(409, str(e)) from e


@router.post("/interview/{token}/person")
def ask_for_person(token: str, db: Session = Depends(get_db)):
    cand = _cand(db, token)
    try:
        request_person(db, cand)
    except PermissionError as e:
        raise HTTPException(409, str(e)) from e
    return {"ok": True, "message": "Thank you. A recruiter will contact you to arrange an interview with a person."}


@router.get("/interview/{token}/diagram/{diagram_id}")
def diagram(token: str, diagram_id: str, db: Session = Depends(get_db)):
    cand = _cand(db, token)
    s = db.query(InterviewSession).filter_by(candidate_id=cand.id).first()
    allowed = {load_questions()[p["question_id"]].get("diagram") for p in (s.plan or [])} if s else set()
    p = diagram_path(diagram_id)
    if diagram_id not in allowed or p is None or not p.exists():
        raise HTTPException(404, "That diagram is not part of your interview")
    return FileResponse(p, media_type="image/png")


# ---- the recruiter's side -------------------------------------------------------------------------------------------------------
@router.get("/interviews")
def interviews(request: Request, user: User = Depends(STAFF), db: Session = Depends(get_db)):
    rows = []
    for c in db.scalars(select(Candidate).where(Candidate.stage.in_(["SHORTLISTED", "AI_INTERVIEW", "HUMAN_INTERVIEW", "DECISION"])).order_by(Candidate.id)):
        s = db.query(InterviewSession).filter_by(candidate_id=c.id).first()
        rows.append({"c": c, "s": s, "blind": make_blind(c)})
    return render(request, "interviews.html", user, rows=rows)


@router.post("/interviews/{cand_id}/invite")
def invite(request: Request, cand_id: int, reason: str = Form(""), user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    """A person invites a SHORTLISTED candidate (a reason is required: the supervisor refuses a person's move without one). This creates the
    interview record, with the plan, and drafts the invitation email."""
    cand = db.get(Candidate, cand_id)
    if cand is None:
        raise HTTPException(404, "That candidate does not exist")
    try:
        move(db, cand, Stage.AI_INTERVIEW, user.email, reason)
        get_or_create_session(db, cand).plan = [p.model_dump() for p in build_plan(db, cand.id, db.get(Requisition, cand.requisition_id)).items]
        from app.agents.communications import draft_invitation
        draft_invitation(db, cand, kind="ai_interview")
    except MoveRefused as e:
        db.rollback()
        flash(request, f"Refused: {e}", "bad")
    else:
        db.commit()
        flash(request, f"Candidate #{cand.id} moved to AI_INTERVIEW. An invitation was drafted: approve it in the outbox before it is sent.")
    return RedirectResponse("/interviews", status_code=303)


@router.post("/interviews/{cand_id}/replay")
def replay(request: Request, cand_id: int, quality: str = Form("strong"), user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    """Demo: run the whole interview from the recorded answers (only in fake mode)."""
    cand = db.get(Candidate, cand_id)
    if cand is None or cand.stage != "AI_INTERVIEW":
        flash(request, "The candidate must be invited to the AI interview first.", "bad")
    elif not get_settings().fake_models:
        flash(request, "Replaying recorded answers is only available in fake mode.", "bad")
    else:
        run_recorded_interview(db, cand, db.get(Requisition, cand.requisition_id), quality)
        flash(request, f"Interview for candidate #{cand.id} replayed from recorded answers. Review the scorecard below.")
    return RedirectResponse(f"/interviews/{cand_id}", status_code=303)


@router.get("/interviews/{cand_id}")
def interview_review(request: Request, cand_id: int, user: User = Depends(STAFF), db: Session = Depends(get_db)):
    """The scorecard for one interview (the interview id is the candidate's id). Audio stays hidden until the recruiter has entered their own
    level for every must-have skill: judge what was said, not how it sounded."""
    cand = db.get(Candidate, cand_id)
    if cand is None:
        raise HTTPException(404, "That candidate does not exist")
    s = db.query(InterviewSession).filter_by(candidate_id=cand_id).first()
    card = build_card(db, s) if s and s.status == "DONE" and s.scorecard else None
    timeline = recording.load_timeline(s) if s and card else None
    from app.models_ext import EvidenceCheck
    check = db.scalars(select(EvidenceCheck).where(EvidenceCheck.candidate_id == cand_id, EvidenceCheck.subject == "interview")).first() if card else None
    return render(request, "interview_review.html", user, cand=cand, s=s, card=card, check=check, timeline=timeline, qs=load_questions(), blind=make_blind(cand),
                  audio_open=bool(s and s.review), has_mp3=bool(s and recording.mp3_path(s).exists()))


@router.post("/interviews/{cand_id}/review")
async def save_review(request: Request, cand_id: int, user: User = Depends(RECRUITER), db: Session = Depends(get_db)):
    """The recruiter's own review: a level (0-3) for every must-have skill, entered from the transcripts, before any audio is shown."""
    s = db.query(InterviewSession).filter_by(candidate_id=cand_id).first()
    if s is None or s.status != "DONE":
        flash(request, "There is no finished interview to review yet.", "bad")
        return RedirectResponse(f"/interviews/{cand_id}", status_code=303)
    card = build_card(db, s)
    form = await request.form()
    levels: dict[str, int] = {}
    for n, row in enumerate(card["skills"]):
        if not row["must_have"]:
            continue
        raw = str(form.get(f"level_{n}", "")).strip()
        if raw not in ("0", "1", "2", "3"):
            flash(request, f"Enter your own level (0 to 3) for {row['skill']} before the audio is shown.", "bad")
            return RedirectResponse(f"/interviews/{cand_id}", status_code=303)
        levels[row["skill"]] = int(raw)
    s.review = {"levels": levels, "note": str(form.get("note", "")).strip()[:500], "by": user.email, "at": datetime.now(timezone.utc).isoformat()}
    s.reviewed_by = user.email
    db.add(DecisionLog(actor=user.email, action="AI interview scorecard reviewed", subject=f"candidate:{cand_id}",
                       reason=f"own levels for {len(levels)} must-have skill(s) entered from the transcript; AI overall {card['overall_100']}/100; "
                              f"{len(card['scorers_disagree'])} scorer disagreement(s) read",
                       evidence={"review": s.review, "ai_levels": {r["skill"]: r["level"] for r in card["skills"]}, "scorers_disagree": card["scorers_disagree"]}))
    db.commit()
    flash(request, "Your review is saved. The audio is now available.")
    return RedirectResponse(f"/interviews/{cand_id}", status_code=303)


@router.post("/interviews/{cand_id}/decision")
def interview_decision(request: Request, cand_id: int, decision: str = Form(""), reason: str = Form(""), user: User = Depends(RECRUITER),
                       db: Session = Depends(get_db)):
    """The recruiter decides what happens next: "Human interview" or "Withdraw", through supervisor.move with a required reason."""
    cand = db.get(Candidate, cand_id)
    s = db.query(InterviewSession).filter_by(candidate_id=cand_id).first()
    if cand is None or s is None:
        raise HTTPException(404, "That interview does not exist")
    try:
        if s.status != "DONE" or not s.review:
            raise MoveRefused("Review the scorecard and enter your own levels first: the decision comes after your own review.")
        from app.agents.checker import explain_refusal, unacknowledged

        pending = unacknowledged(db, cand_id, "interview")
        if pending:
            raise MoveRefused(explain_refusal(pending))
        card = build_card(db, s)
        evidence = {"overall_100": card["overall_100"], "review": s.review, "scorers_disagree": card["scorers_disagree"]}
        if decision == "human_interview":
            move(db, cand, Stage.HUMAN_INTERVIEW, user.email, reason, evidence=evidence)
            from app.agents.communications import draft_invitation

            draft_invitation(db, cand, kind="invitation")
        elif decision == "withdraw":
            move(db, cand, Stage.WITHDRAWN, user.email, reason, evidence=evidence)
        else:
            raise MoveRefused("Choose Human interview or Withdraw.")
    except MoveRefused as e:
        db.rollback()
        flash(request, f"Not recorded: {e}", "bad")
    else:
        db.commit()
        flash(request, "Your decision and reason are in the decision log." + (" An invitation with a proposed slot is waiting in the outbox for your approval." if decision == "human_interview" else ""))
    return RedirectResponse(f"/interviews/{cand_id}", status_code=303)


@router.get("/media/interview/{cand_id}")
def media(cand_id: int, ref: str, user: User = Depends(STAFF), db: Session = Depends(get_db)):
    """Interview audio, for the 'play the moment' links. Only staff, and only files under the kit or the interview storage folder."""
    roots = [Path(get_settings().kit_dir).resolve(), (get_settings().storage_dir / "interviews").resolve()]
    for root in roots:
        p = (root / ref).resolve() if not Path(ref).is_absolute() else Path(ref).resolve()
        if p.exists() and any(str(p).startswith(str(r)) for r in roots):
            return FileResponse(p)
    p = (get_settings().storage_dir / ref).resolve()
    if p.exists() and str(p).startswith(str((get_settings().storage_dir / "interviews").resolve())):
        return FileResponse(p)
    raise HTTPException(404, "That recording is not available")


# ---- the recording (staff only; every opening is written to the decision log) ------------------------------------------------------------------
def _logged_recording(db: Session, user: User, interview_id: int, what: str) -> InterviewSession:
    s = db.get(InterviewSession, interview_id)
    if s is None or not s.consent_recording:
        raise HTTPException(404, "There is no recording for that interview")
    db.add(DecisionLog(actor=user.email, action="recording opened", subject=f"interview:{interview_id}", reason=f"{user.role} opened the {what}",
                       evidence={"candidate_id": s.candidate_id, "what": what}))
    db.commit()
    return s


@router.get("/interviews/{interview_id}/recording")
def recording_audio(interview_id: int, user: User = Depends(STAFF), db: Session = Depends(get_db)):
    s = _logged_recording(db, user, interview_id, "audio")
    if not recording.mp3_path(s).exists():
        raise HTTPException(404, "The recording has not been built yet, or has been deleted after the retention period")
    return FileResponse(recording.mp3_path(s), media_type="audio/mpeg", filename="full_conversation.mp3")


@router.get("/interviews/{interview_id}/recording.json")
def recording_timeline(interview_id: int, user: User = Depends(STAFF), db: Session = Depends(get_db)):
    s = _logged_recording(db, user, interview_id, "timeline")
    doc = recording.load_timeline(s)
    if doc is None:
        raise HTTPException(404, "The recording has not been built yet, or has been deleted after the retention period")
    return JSONResponse(doc)


# ---- the replay room (staff; opens only after the recruiter's own review; every opening is logged) -----------------------------------------------
def _replay_ready(db: Session, cand_id: int):
    """The interview and its timeline, or the reason the replay cannot open yet."""
    s = db.query(InterviewSession).filter_by(candidate_id=cand_id).first()
    if s is None or s.status != "DONE" or not s.consent_recording:
        return None, "There is no recorded interview to replay."
    if not s.review:
        return None, "Enter your own levels for the must-have skills first: the replay comes after your own review (judge what was said, not how it sounded)."
    if not recording.mp3_path(s).exists() or recording.load_timeline(s) is None:
        return None, "The recording has not been built yet, or was deleted after the retention period."
    return s, ""


@router.get("/interviews/{cand_id}/replay")
def replay_room(request: Request, cand_id: int, user: User = Depends(STAFF), db: Session = Depends(get_db)):
    cand = db.get(Candidate, cand_id)
    if cand is None:
        raise HTTPException(404, "That candidate does not exist")
    s, why = _replay_ready(db, cand_id)
    if s is None:
        flash(request, why, "bad")
        return RedirectResponse(f"/interviews/{cand_id}", status_code=303)
    timeline = recording.load_timeline(s)
    seen, diagrams = set(), []
    for c in timeline["clips"]:
        if c.get("diagram") and c["diagram"] not in seen:
            seen.add(c["diagram"])
            diagrams.append({"text": c["diagram"], "title": c.get("diagram_title") or ""})
    db.add(DecisionLog(actor=user.email, action="replay opened", subject=f"interview:{s.id}", reason=f"{user.role} opened the replay room",
                       evidence={"candidate_id": cand_id}))
    db.commit()
    return render(request, "replay.html", user, cand=cand, s=s, sample=bool(s.sample), timeline=timeline, diagrams=diagrams)


@router.get("/interviews/{cand_id}/replay/audio")
def replay_audio(cand_id: int, user: User = Depends(STAFF), db: Session = Depends(get_db)):
    """The audio for the replay page (the page's opening is what is logged; the player may ask for it in several pieces)."""
    s, why = _replay_ready(db, cand_id)
    if s is None:
        raise HTTPException(403, why)
    return FileResponse(recording.mp3_path(s), media_type="audio/mpeg")
