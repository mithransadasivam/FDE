"""Day 2 prompt 12: the full interview recording, its timeline, the staff-only routes and the purge."""
import json
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.ai import audio
from app.config import get_settings
from app.interview import recording
from app.interview.replay import load_recorded, run_recorded_interview
from app.models import Candidate, DecisionLog, Requisition
from app.models_ext import InterviewSession
from scripts.purge_recordings import purge
from tests.test_interview import invited, shortlisted, token  # noqa: F401


@pytest.fixture
def finished(invited, db):
    """A finished interview with a recording, made through the real routes (the last answer builds it in the background)."""
    t = token(db)
    invited.visitor.post(f"/interview/{t}/notice", data={"agree": "yes"})
    prompt = invited.visitor.post(f"/interview/{t}/start").json()["prompt"]
    while prompt:
        res = invited.visitor.post(f"/interview/{t}/answer", data={"text": "I would check the logs, memory and the disk, and what changed recently."}).json()
        if res["done"]:
            break
        prompt = res["next"]
    db.expire_all()
    return invited, db.query(InterviewSession).one()


def test_a_finished_interview_has_an_mp3_and_a_timeline_that_adds_up(finished):
    _, s = finished
    mp3, doc = recording.mp3_path(s), recording.load_timeline(s)
    assert mp3.exists() and doc and s.recording_built_at is not None
    clips = doc["clips"]
    assert clips[0]["speaker"] == "interviewer" and clips[1]["speaker"] == "candidate"  # question, then answer, in order
    assert [c["n"] for c in clips] == list(range(1, len(clips) + 1))
    for prev, nxt in zip(clips, clips[1:]):
        assert nxt["start"] >= prev["end"]  # in order, no overlaps
    assert abs(audio.duration(mp3) - doc["duration"]) <= 1.0  # the timeline adds up to the file length, within a second
    assert abs(clips[-1]["end"] - doc["duration"]) < 0.05
    assert any(c["level"] is not None and c["quote"] for c in clips if c["speaker"] == "candidate")  # scored answers carry the level and the quote
    assert any(c["kind"] == "follow_up" for c in clips) or any(c["kind"] == "opening" for c in clips)
    assert doc["clips"][0]["kind"] == "opening" and doc["clips"][0]["text"].startswith("Please describe your most recent role")


def test_the_gap_between_clips_is_half_a_second(finished):
    _, s = finished
    clips = recording.load_timeline(s)["clips"]
    assert round(clips[1]["start"] - clips[0]["end"], 2) == 0.5


def test_staff_can_open_the_recording_and_every_opening_is_logged(finished, db):
    c, s = finished
    r = c.rc.get(f"/interviews/{s.id}/recording")
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and len(r.content) > 1000
    assert c.hm.get(f"/interviews/{s.id}/recording.json").json()["interview_id"] == s.id
    db.expire_all()
    opened = db.query(DecisionLog).filter(DecisionLog.action == "recording opened").all()
    assert [o.actor for o in opened] == ["recruiter@example.com", "hm@example.com"] and all(o.at for o in opened)


def test_a_candidate_or_a_signed_out_visitor_cannot_fetch_a_recording(finished, db):
    c, s = finished
    for path in (f"/interviews/{s.id}/recording", f"/interviews/{s.id}/recording.json"):
        assert c.visitor.get(path).status_code in (303, 401, 403)
        assert c.visitor.get(path, headers={"Authorization": f"Bearer {token(db)}"}).status_code in (303, 401, 403)
    db.expire_all()
    assert db.query(DecisionLog).filter(DecisionLog.action == "recording opened").count() == 0


def test_an_interview_without_recording_consent_is_not_recorded(invited, db):
    s = InterviewSession(id=1, candidate_id=1, status="DONE", notice_ack=True, consent_recording=False, state={"turns": []}, scorecard={})
    db.merge(s)
    db.commit()
    assert recording.build_recording(db, db.get(InterviewSession, 1)) is None
    assert invited.rc.get("/interviews/1/recording").status_code == 404


def test_the_recording_can_be_built_for_a_demo_replay_with_recorded_answers(invited, db):
    run_recorded_interview(db, db.get(Candidate, 1), db.get(Requisition, 1), "strong", build=True)
    db.expire_all()
    s = db.query(InterviewSession).one()
    doc = recording.load_timeline(s)
    assert doc and recording.mp3_path(s).exists() and abs(audio.duration(recording.mp3_path(s)) - doc["duration"]) <= 1.0
    answered = [c for c in doc["clips"] if c["speaker"] == "candidate"]
    assert any(c["end"] - c["start"] > 2 for c in answered)  # the recorded answers are real audio, not placeholders


def test_purge_deletes_old_audio_and_logs_each_file_and_keeps_recent_audio(finished, db):
    _, s = finished
    folder = recording.folder_of(s)
    files = sorted(p.name for p in folder.glob("*") if p.suffix in recording.AUDIO_SUFFIXES)
    assert "full_conversation.mp3" in files and len(files) > 3
    dry = purge(db, dry_run=True)
    assert dry["files_deleted"] == 0  # nothing is old yet
    assert purge(db)["files_deleted"] == 0 and (folder / "full_conversation.mp3").exists()
    s.ended_at = datetime.now(timezone.utc) - timedelta(days=get_settings().retention_days + 5)
    db.commit()
    assert purge(db, dry_run=True)["files_deleted"] == len(files) and (folder / "full_conversation.mp3").exists()
    out = purge(db)
    assert out["files_deleted"] == len(files) and out["interviews"] == [s.id]
    assert not [p for p in folder.glob("*") if p.suffix in recording.AUDIO_SUFFIXES]
    db.expire_all()
    deleted = db.query(DecisionLog).filter(DecisionLog.action == "interview audio deleted").all()
    assert len(deleted) == len(files) and {d.evidence["file"] for d in deleted} == set(files)
    assert db.query(InterviewSession).one().recording_built_at is None
