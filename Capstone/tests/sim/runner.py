"""Runs a whole interview with a simulated candidate through the SAME functions the routes use (InterviewerAgent.start / submit), and builds
the recording. Used by tests/test_interview_sim.py and scripts/make_sample_interviews.py."""
from sqlalchemy.orm import Session

from app.agents.interviewer import MAX_SECONDS, InterviewerAgent, get_or_create_session
from app.ai import audio, speech, voice
from app.config import get_settings
from app.interview.recording import build_recording
from app.models import Candidate, Requisition
from tests.sim.candidate import SimulatedCandidate


def run_interview(db: Session, cand: Candidate, req: Requisition, persona: str, profile: dict | None = None, extra_seconds_per_turn: float = 0.0,
                  speak: bool = False, build: bool = True, max_turns: int = 80) -> dict:
    """The candidate has been invited. They agree to recording, answer every question as `persona`, and the interview runs to its end.
    speak=True: the interviewer speaks with the real interviewer voice and the answers are spoken with a different voice and saved as audio.
    extra_seconds_per_turn adds time to each answer (to test the time limit). Returns the last result (the scorecard is in result['scorecard'])."""
    s = get_or_create_session(db, cand)
    s.notice_ack, s.consent_recording, s.sample = True, True, True  # a simulated candidate: always labelled as a sample
    db.commit()
    agent = InterviewerAgent(db, s)
    agent.real_voice = speak
    sim = SimulatedCandidate(persona, profile)
    prompt = agent.start(req, opening=True)
    result: dict = {}
    for _ in range(max_turns):
        text = sim.answer(prompt)
        ref, seconds = None, voice.speaking_seconds(text)
        if speak:
            path = agent.folder / f"turn_{agent.question_number():02d}_answer.wav"
            if speech.speak(text, path, voice="candidate", real=True):
                ref, seconds = str(path.relative_to(get_settings().storage_dir)).replace("\\", "/"), audio.duration(path)
        result = agent.submit(text=text, audio_ref=ref, duration_s=seconds + extra_seconds_per_turn)
        if result.get("done"):
            break
        prompt = result["next"]
    if build and result.get("done"):
        build_recording(db, s)
    result["elapsed_s"] = s.state["elapsed_s"]
    result["time_limit_s"] = MAX_SECONDS
    return result
