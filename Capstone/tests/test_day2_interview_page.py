"""Day 2 prompt 8: the interview page: a question spoken into a saved file, an answer recorded and transcribed, record again, audio only."""
import wave
from pathlib import Path

from app.ai import speech
from app.config import get_settings
from app.interview.replay import load_recorded
from app.models_ext import InterviewSession, InterviewTurn
from tests.conftest import KIT, ROOT
from tests.test_interview import invited, shortlisted, token  # noqa: F401


def folder(db) -> Path:
    return get_settings().storage_dir / "interviews" / str(db.query(InterviewSession).one().id)


def begin(invited, db):
    t = token(db)
    invited.visitor.post(f"/interview/{t}/notice", data={"agree": "yes"})
    return t, invited.visitor.post(f"/interview/{t}/start").json()["prompt"]


def test_speak_writes_a_wav_in_fake_mode_and_a_real_one_when_asked(tmp_path):
    p = speech.speak("Hello there", tmp_path / "a.wav")
    with wave.open(str(p), "rb") as w:
        assert w.getnframes() > 0 and w.getframerate() == 16000
    real = speech.speak("Hello there, this is a test.", tmp_path / "b.wav", real=True)
    assert real is None or real.stat().st_size > 2000  # a real voice if the machine has one; never a crash


def test_start_creates_turn_one_with_the_fixed_opening_question_and_saves_its_audio(invited, db):
    t, prompt = begin(invited, db)
    assert prompt["opening"] and prompt["text"] == "Please describe your most recent role and what you were responsible for."
    assert prompt["audio"].endswith("turn_01_question.wav") and (get_settings().storage_dir / prompt["audio"]).exists()
    r = invited.visitor.get(f"/interview/{t}/audio/turn_01_question.wav")
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav"
    db.expire_all()
    row = db.query(InterviewTurn).one()
    assert row.n == 1 and row.kind == "opening" and row.question_audio.endswith("turn_01_question.wav") and row.shown_at is not None
    assert invited.visitor.get(f"/interview/{t}/audio/turn_01_answer.webm").status_code == 404  # answers are never served to the page


def test_record_then_submit_saves_both_audio_files_and_transcribes(invited, db):
    t, _ = begin(invited, db)
    rec = next(a for a in load_recorded() if a["kind"] == "strong")
    wav = (KIT / rec["file"]).read_bytes()
    r = invited.visitor.post(f"/interview/{t}/record", files={"audio": (Path(rec["file"]).name, wav, "audio/wav")})
    assert r.status_code == 200 and r.json()["transcript"]
    answer_file = folder(db) / "turn_01_answer.wav"
    assert answer_file.exists()  # saved straight away, but nothing is scored until the candidate submits
    db.expire_all()
    assert db.query(InterviewSession).one().state["turns"][0]["answers"] == []
    res = invited.visitor.post(f"/interview/{t}/submit").json()
    assert res["next"]["number"] == 1 and not res["done"]
    db.expire_all()
    turn = db.query(InterviewTurn).filter_by(n=1).one()
    assert turn.answer_audio.endswith("turn_01_answer.wav") and turn.transcript and turn.answer_ended_at is not None
    assert (folder(db) / "turn_01_question.wav").exists() and (folder(db) / "turn_02_question.wav").exists()


def test_record_again_deletes_the_discarded_recording_at_once(invited, db):
    t, _ = begin(invited, db)
    rec = next(a for a in load_recorded() if a["kind"] == "strong")
    wav = (KIT / rec["file"]).read_bytes()
    invited.visitor.post(f"/interview/{t}/record", files={"audio": (Path(rec["file"]).name, wav, "audio/wav")})
    assert (folder(db) / "turn_01_answer.wav").exists()
    assert invited.visitor.post(f"/interview/{t}/discard").status_code == 200
    assert not (folder(db) / "turn_01_answer.wav").exists()
    assert invited.visitor.post(f"/interview/{t}/submit").status_code == 409  # nothing left to submit
    # recording again and submitting leaves exactly one answer file
    invited.visitor.post(f"/interview/{t}/record", files={"audio": (Path(rec["file"]).name, wav, "audio/wav")})
    invited.visitor.post(f"/interview/{t}/submit")
    assert sorted(p.name for p in folder(db).glob("turn_01_*")) == ["turn_01_answer.wav", "turn_01_question.wav"]


def test_a_recording_that_cannot_be_read_gives_a_clear_error_and_leaves_no_file(invited, db):
    t, _ = begin(invited, db)
    r = invited.visitor.post(f"/interview/{t}/record", files={"audio": ("answer.webm", b"this is not audio", "audio/webm")})
    assert r.status_code == 422 and "recording" in r.json()["detail"].lower()
    assert not list(folder(db).glob("turn_01_answer*"))


def test_the_page_asks_for_the_microphone_only_and_never_the_camera():
    html = (ROOT / "templates" / "interview.html").read_text(encoding="utf-8")
    assert "getUserMedia({ audio: true })" in html and "video" not in html.lower() and "camera" not in html.lower().replace("no camera", "")
    for needle in ("MediaRecorder", "microphone is blocked", "Record again", "Submit this answer", "Play again", "Time left", "level-bar"):
        assert needle.lower() in html.lower(), needle
