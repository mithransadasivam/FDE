"""Day 3 prompt 4: a generated recruiter-led practice interview with five labelled planned moments."""
import json
import sys

import pytest

from app import guardrails
from app.ai import audio
from app.models import Candidate
from app.practice import MOMENTS, folder_for, load_practice, make_practice
from app.privacy import identity_strings
from tests.test_interview import shortlisted, token  # noqa: F401


@pytest.fixture
def practice(shortlisted, db):
    return make_practice(db, db.get(Candidate, 1), speak_real=False)  # silent audio of the right length: fast; the voices are checked separately


def test_the_practice_interview_has_a_timed_script_and_the_five_planned_moments(practice):
    assert practice["sample"] and practice["label"] == "SAMPLE: fictional" and practice["kind"] == "practice"
    assert set(practice["moments"]) == set(MOMENTS)
    lines = practice["lines"]
    assert 12 <= len(lines) <= 24 and lines[0]["speaker"] == "recruiter" and {l["speaker"] for l in lines} == {"recruiter", "candidate"}
    for prev, nxt in zip(lines, lines[1:]):
        assert nxt["start"] >= prev["end"] and prev["start"] < prev["end"]
    for m, info in practice["moments"].items():
        row = lines[info["line"] - 1]
        assert row["moment"] == m and info["start"] == row["start"] and info["end"] == row["end"]
    assert practice["duration_s"] == pytest.approx(lines[-1]["end"], abs=0.05)


def test_the_moments_are_what_they_say_they_are(practice):
    lines, moments = practice["lines"], practice["moments"]
    assert guardrails.forbidden_question(lines[moments["forbidden_question"]["line"] - 1]["text"])  # the rules catch it
    assert lines[moments["forbidden_question"]["line"] - 1]["speaker"] == "recruiter"
    good, vague = lines[moments["good_technical_answer"]["line"] - 1], lines[moments["vague_answer"]["line"] - 1]
    assert good["speaker"] == vague["speaker"] == "candidate" and len(good["text"].split()) > 3 * len(vague["text"].split())
    claim = moments["cv_conflict"]
    assert claim["claimed_years"] >= claim["cv_years"] + 4 and str(claim["claim"]).split()[0] in lines[claim["line"] - 1]["text"]  # far more years than the CV shows
    beh = lines[moments["behavioural_answer"]["line"] - 1]["text"].lower()
    assert all(w in beh for w in ("situation", "task", "acknowledged", "result"))  # a full example


def test_it_is_generated_from_the_candidate_and_the_job_and_names_nobody(practice, shortlisted, db):
    for c in db.query(Candidate):
        for secret in identity_strings(c.profile):
            assert secret.lower() not in json.dumps(practice).lower(), secret
    other = make_practice(db, db.get(Candidate, 2), speak_real=False)
    assert [l["text"] for l in other["lines"]] != [l["text"] for l in practice["lines"]] or other["moments"] != practice["moments"]


def test_the_files_are_written_and_the_audio_matches_the_timeline(practice):
    folder = folder_for(1)
    assert (folder / "practice.wav").exists() and (folder / "practice.json").exists() and load_practice(1)["id"] == "P-001"
    assert abs(audio.duration(folder / "practice.wav") - practice["duration_s"]) < 1.0
    assert not (folder / "_work").exists()  # the temporary clips are cleaned up


def test_the_script_runs_for_a_shortlisted_candidate_only(shortlisted, db, monkeypatch, capsys):
    from scripts import make_recruiter_interview as script

    monkeypatch.setattr(sys, "argv", ["x", "--candidate", "1", "--silent"])
    assert script.main() == 0
    out = capsys.readouterr().out
    assert "SAMPLE: fictional" in out and all(m in out for m in MOMENTS)
    db.get(Candidate, 1).stage = "SCREENED"
    db.commit()
    assert script.main() == 1


def test_two_clearly_different_voices_when_the_machine_has_voices(shortlisted, db):
    doc = make_practice(db, db.get(Candidate, 1), speak_real=True)
    from app.ai import speech

    if speech.speak("hello", folder_for(1) / "probe.wav", real=True) is None:
        pytest.skip("no text-to-speech voice on this machine")
    assert doc["duration_s"] > 30  # real speech: a minute or more of audio
