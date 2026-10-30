"""Day 4 prompt 5: every model call is logged with its cost and time; the Trust and cost page and the cost report read those logs; the speech cache is safe and measurable."""
import pytest
from sqlalchemy import select

from app import costing, timing
from app.ai import ledger, speech
from app.config import get_settings
from app.db import OpsSession, init_ops_db
from app.interview.bank import load_questions
from app.models import Candidate, Requisition
from app.models_ext import ModelCall, ResponseTiming
from tests.sim.runner import run_interview
from tests.test_interview import invited, shortlisted, token  # noqa: F401


@pytest.fixture(autouse=True)
def clean_ops():
    init_ops_db()
    with OpsSession() as o:
        o.query(ModelCall).delete()
        o.query(ResponseTiming).delete()
        o.commit()


def _call(agent, cost, candidate, tier="large", simulated=False):
    ledger.record_call(agent, "scoring", tier, "m", "sys", "user", "out", 12.0, simulated=simulated, candidate_id=candidate, cost=cost)


def test_the_ledger_stores_the_providers_own_cost_when_there_is_one():
    _call("screening", 0.0123, 1)
    with OpsSession() as o:
        row = o.scalars(select(ModelCall)).one()
    assert row.cost_usd == 0.0123 and row.latency_ms == 12.0 and row.tokens_in > 0 and row.agent == "screening"


def test_a_call_without_a_provider_cost_falls_back_to_the_list_price():
    ledger.record_call("screening", "scoring", "large", "m", "s" * 4000, "u" * 4000, "o" * 400, 5.0, simulated=True, candidate_id=1)
    with OpsSession() as o:
        assert o.scalars(select(ModelCall)).one().cost_usd > 0


def test_transcription_and_speech_calls_are_logged_with_no_cost():
    ledger.record_timed("voice", "transcription", 1.5, candidate_id=2)
    with OpsSession() as o:
        row = o.scalars(select(ModelCall)).one()
    assert row.cost_usd == 0.0 and row.latency_ms == 1500.0 and row.tier == "local"


def test_the_numbers_are_per_unit_from_the_logged_calls():
    for cand in (1, 2):
        _call("document", 0.0, cand)
        _call("screening", 0.01, cand)
        _call("checker", 0.002, cand)
    _call("interviewer", 0.03, 1)
    _call("interviewer", 0.01, 1)
    _call("diagrams", 0.005, 1)
    _call("copilot", 0.02, 1)
    c = costing.cost_numbers()
    assert c["per_cv_screened"]["per_unit"] == pytest.approx(0.012) and c["per_cv_screened"]["units"] == 2
    assert c["per_100_cvs"] == pytest.approx(1.2)
    assert c["per_interview"]["per_unit"] == pytest.approx(0.045) and c["per_interview"]["units"] == 1
    assert c["per_copilot_session"]["per_unit"] == pytest.approx(0.02)
    assert list(c["by_agent"])[0] == "interviewer"  # most expensive first
    assert c["total_cost"] == pytest.approx(0.01 * 2 + 0.002 * 2 + 0.045 + 0.02)


def test_the_stopwatch_splits_one_answer_into_its_steps_and_saves_it():
    import time

    timing.begin(transcription_s=0.5)
    with timing.timed("scoring"):
        time.sleep(0.02)
    with timing.timed("speech"):
        time.sleep(0.03)
    row = timing.finish(7, 3)
    assert row["transcription"] == 0.5 and row["scoring"] >= 0.02 and row["speech"] >= 0.03 and row["total_s"] == pytest.approx(sum(row[s] for s in timing.STEPS), abs=1e-3)
    with OpsSession() as o:
        saved = o.scalars(select(ResponseTiming)).one()
    assert saved.candidate_id == 7 and saved.turn == 3


def test_timed_does_nothing_when_no_answer_is_being_timed():
    with timing.timed("scoring"):
        pass
    assert timing.finish(1) is None


def test_a_simulated_interview_is_timed_step_by_step(invited, db):
    run_interview(db, db.get(Candidate, 1), db.get(Requisition, 1), "strong")
    s = costing.speed_numbers()
    assert s["answers"] >= 6 and set(s["steps"]) == set(timing.STEPS) and s["total"]["slowest"] >= s["total"]["median"] > 0
    assert s["slowest_step_overall"] in timing.STEPS


def test_the_trust_page_shows_cost_speed_and_the_latest_reports(invited, db):
    run_interview(db, db.get(Candidate, 1), db.get(Requisition, 1), "strong")
    html = invited.rc.get("/trust").text
    for text in ("Cost, from the logged calls", "Per 100 CVs", "Per AI interview", "Per copilot session", "How fast the interviewer replies", "Whole reply", "Latest test reports",
                 "Identity swap", "Accent test", "Attack tests", "Copilot evaluation"):
        assert text in html, text
    assert invited.hm.get("/trust").status_code == 200


def test_the_latest_reports_come_from_the_report_files():
    names = {r["name"]: r for r in costing.latest_reports()}
    assert set(names) == {"identity_swap", "accent_test", "attack_report", "copilot_eval"}
    for r in names.values():
        assert r["status"] in ("PASS", "FAIL", "not run")


# ---- the improvement: a fixed question is spoken once ------------------------------------------------------------------------------------
def test_a_fixed_question_is_spoken_once_and_reused(tmp_path, monkeypatch):
    spoken = []

    def fake_voice(text, path, voice):
        spoken.append(text)
        path.write_bytes(b"RIFF" + b"0" * 2000)
        return True

    monkeypatch.setattr(speech, "_pyttsx3", fake_voice)
    fixed = next(iter(load_questions().values()))["question"]
    a = speech.speak(fixed, tmp_path / "a.wav", real=True)
    b = speech.speak(fixed, tmp_path / "b.wav", real=True)
    assert a and b and spoken == [fixed] and (tmp_path / "b.wav").read_bytes() == (tmp_path / "a.wav").read_bytes()


def test_a_written_question_is_never_cached_because_it_mentions_the_cv(tmp_path, monkeypatch):
    spoken = []
    monkeypatch.setattr(speech, "_pyttsx3", lambda text, path, voice: (spoken.append(text), path.write_bytes(b"RIFF" + b"0" * 2000), True)[2])
    written = "You mention running Terraform at Acme. How did you keep the state safe?"
    speech.speak(written, tmp_path / "a.wav", real=True)
    speech.speak(written, tmp_path / "b.wav", real=True)
    assert spoken == [written, written]


def test_the_speech_cache_can_be_switched_off(tmp_path, monkeypatch):
    spoken = []
    monkeypatch.setattr(speech, "_pyttsx3", lambda text, path, voice: (spoken.append(text), path.write_bytes(b"RIFF" + b"0" * 2000), True)[2])
    monkeypatch.setattr(get_settings(), "speech_cache", False)
    fixed = next(iter(load_questions().values()))["question"]
    speech.speak(fixed, tmp_path / "a.wav", real=True)
    speech.speak(fixed, tmp_path / "b.wav", real=True)
    assert len(spoken) == 2
