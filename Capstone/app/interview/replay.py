"""Runs a whole AI interview from the recorded answers (used by the demo, the evaluation and the tests)."""
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.agents.interviewer import InterviewerAgent, get_or_create_session
from app.config import get_settings
from app.interview.bank import load_questions
from app.models import Candidate, DecisionLog, Requisition


def load_recorded() -> list[dict]:
    path = Path(get_settings().kit_dir) / "recorded_answers" / "answers.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def run_recorded_interview(db: Session, cand: Candidate, req: Requisition, quality: str = "strong", build: bool = False) -> dict:
    """The candidate acknowledges the notice (recorded as a demo replay), then every question is answered from a recorded file.
    quality is the kind of recorded answer to prefer: strong, partial or weak. When a follow-up is asked, the 'candidate'
    adds the first key point they had missed, so the follow-up visibly raises the score."""
    recorded = load_recorded()
    bank = load_questions()
    session = get_or_create_session(db, cand)
    if not session.notice_ack:
        session.notice_ack, session.consent_recording = True, True
        db.add(DecisionLog(actor="candidate", action="AI notice acknowledged", subject=f"candidate:{cand.id}", reason="demo replay from recorded answers"))
    agent = InterviewerAgent(db, session)
    prompt = agent.start(req, opening=True)
    kit = Path(get_settings().kit_dir)
    result: dict = {}
    while prompt:
        if prompt.get("opening"):  # the fixed opening question is answered, not scored
            result = agent.submit(text="In my most recent role I handled support tickets for cloud customers and took part in the on-call rota.")
        elif prompt["is_follow_up"]:
            q = bank[prompt["question_id"]]
            turn = session.state["turns"][-1]
            missed = turn["score"]["key_points_missed"]
            say = next((d["say"] for d in q["key_point_detail"] if d["text"] in missed), "I would also check the logs.")
            result = agent.submit(text=say)
        else:
            pool = [a for a in recorded if a["question_id"] == prompt["question_id"] and a["kind"] in (quality, "partial", "weak", "strong")]
            pick = next((a for a in pool if a["kind"] == quality), pool[0] if pool else None)
            if pick is None:
                result = agent.submit(text="I am not sure about this one.")
            else:
                path = kit / pick["file"]
                result = agent.submit(audio_path=path, original_name=path.name, audio_ref=pick["file"])
        prompt = result.get("next")
        if result.get("done"):
            break
    if result.get("done") and build:
        from app.interview.recording import build_recording

        build_recording(db, session)
    return result
