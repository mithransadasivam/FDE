import csv
import json
import os
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.agents import interviewer
from app.models import Candidate, DecisionLog
from app.models_ext import InterviewSession
from scripts.governance_check import check
from scripts.purge_expired import purge

ROOT = Path(__file__).resolve().parent.parent


# ---- rule 4: no voice features reach scoring (the "prohibited practices avoided" test) ---------------------------------------------------------
def test_scoring_functions_take_text_only():
    import inspect
    for fn in (interviewer.score_text, interviewer.second_opinion, interviewer.build_answer_prompt):
        params = inspect.signature(fn).parameters
        assert not any(k in params for k in ("audio", "audio_path", "path", "pitch", "pace", "duration", "duration_s", "tone", "emotion", "accent")), fn.__name__
    assert "transcript" in inspect.signature(interviewer.score_text).parameters


def test_the_scoring_prompt_contains_only_the_question_the_guide_and_the_words_said(platform, db, monkeypatch):
    seen = []
    real = interviewer.complete_json

    def spy(system, user, schema, **kw):
        if kw.get("agent") == "interviewer":
            seen.append((system, user))
        return real(system, user, schema, **kw)

    monkeypatch.setattr(interviewer, "complete_json", spy)
    q = interviewer.load_questions()["T-01"]
    # the same words, very different audio facts: a short fast answer and a long slow one
    interviewer.score_text(q, "I would start with top and uptime to see the load.", candidate_id=1)
    assert len(seen) == 1
    system, user = seen[0]
    assert set(re.findall(r"<(\w+)", user)) == {"question", "key_points", "scoring_guide", "answer"}  # nothing else is passed
    for word in ("duration", "seconds", "pitch", "accent", "tone", "wav", "webm", "emotion", "confidence level"):
        assert word not in user.lower()


def test_audio_duration_only_affects_the_time_limit_never_the_score(invited_db):
    db, agent_cls, session = invited_db
    from app.models import Requisition
    agent = agent_cls(db, session)
    agent.start(db.get(Requisition, 1))
    words = "I would start with top and uptime to see the load and which process uses the CPU."
    r1 = agent.submit(text=words, duration_s=5)
    assert r1["score"] is not None
    s1 = r1["score"]["score"]
    # score the same words again with a very different duration through the scoring function
    q = interviewer.load_questions()[r1["score"]["question_id"]]
    assert interviewer.score_text(q, words).score == s1


@pytest.fixture
def invited_db(platform, db):
    platform.apply("C-001_cv.pdf")
    platform.rc.post("/screening/1/run")
    platform.rc.post("/screening/1/approve", data={"reason": "ok", "candidate_id": [1]})
    platform.rc.post("/interviews/1/invite")
    s = interviewer.get_or_create_session(db, db.get(Candidate, 1))
    s.notice_ack = True
    db.commit()
    return db, interviewer.InterviewerAgent, s


def test_no_code_in_the_project_analyses_voice_or_faces():
    banned = ("librosa", "parselmouth", "opensmile", "pyAudioAnalysis", "deepface", "emotion_recognition", "cv2.CascadeClassifier", "mediapipe")
    offenders = []
    for path in list((ROOT / "app").rglob("*.py")) + list((ROOT / "scripts").glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for b in banned:
            if b in text and "banned" not in text.split(b)[0][-80:]:
                offenders.append(f"{path.name}: {b}")
    assert offenders == []
    assert "camera" not in (ROOT / "templates" / "interview.html").read_text(encoding="utf-8").lower().replace("no camera", "")
    assert "video" not in (ROOT / "templates" / "interview.html").read_text(encoding="utf-8").lower()


# ---- retention (rule 10) --------------------------------------------------------------------------------------------------------------------
def test_expired_cvs_and_recordings_are_deleted_and_logged_recent_ones_are_kept(platform, db):
    platform.apply("C-001_cv.pdf")
    platform.apply("C-004_cv.docx")
    old, new = db.get(Candidate, 1), db.get(Candidate, 2)
    old.applied_at = datetime.now(timezone.utc) - timedelta(days=200)
    from app.config import get_settings
    rec = get_settings().storage_dir / "interviews" / "1"
    rec.mkdir(parents=True, exist_ok=True)
    (rec / "a.webm").write_bytes(b"x")
    s = interviewer.get_or_create_session(db, old)
    s.ended_at = datetime.now(timezone.utc) - timedelta(days=200)
    db.commit()
    cv_old, cv_new = Path(old.cv_path), Path(new.cv_path)
    dry = purge(db, dry_run=True)
    assert dry["cvs_deleted"] == 1 and cv_old.exists() and rec.exists()
    out = purge(db)
    assert out["cvs_deleted"] == 1 and out["recordings_deleted"] == 1
    assert not cv_old.exists() and not rec.exists() and cv_new.exists()
    db.expire_all()
    assert db.get(Candidate, 1).cv_path == "" and db.get(Candidate, 2).cv_path
    assert {"CV deleted after retention period", "interview recordings deleted after retention period"} <= {e.action for e in db.query(DecisionLog)}


# ---- the governance pack -----------------------------------------------------------------------------------------------------------------------
@pytest.fixture
def pack(tmp_path, monkeypatch):
    if not (ROOT / "governance" / "model_card.md").exists():
        pytest.skip("run python -m scripts.quality_gate first to build the governance pack")
    shutil.copytree(ROOT / "governance", tmp_path / "governance")
    monkeypatch.chdir(tmp_path)
    return tmp_path / "governance"


def test_the_governance_pack_passes_its_check(pack):
    r = check()
    assert r["passed"], [c for c in r["checks"] if not c["passed"]]
    assert len(r["checks"]) >= 14


def test_risk_register_has_at_least_ten_risks_with_owners(pack):
    rows = list(csv.DictReader((pack / "risk_register.csv").open(encoding="utf-8")))
    assert len(rows) >= 10 and all(r["owner"] and r["control"] and r["review_date"] for r in rows)
    assert {"Govern", "Map", "Measure", "Manage"} <= {r["nist_function"] for r in rows}


def test_changing_a_number_in_the_model_card_fails_the_check(pack):
    card = pack / "model_card.md"
    card.write_text(re.sub(r"(\d+(?:\.\d+)?)(%? \[evidence: eval_extraction\.json#pct\])", lambda m: "50" + m.group(2), card.read_text(encoding="utf-8"), count=1), encoding="utf-8")
    r = check()
    assert not r["passed"] and any("model card" in c["check"] and not c["passed"] for c in r["checks"])


def test_tampering_with_an_evidence_file_fails_the_hash_check(pack):
    f = pack / "evidence" / "eval_extraction.json"
    data = json.loads(f.read_text(encoding="utf-8"))
    data["pct"] = 99.9
    f.write_text(json.dumps(data), encoding="utf-8")
    r = check()
    assert not r["passed"] and any("hash" in c["check"] and not c["passed"] for c in r["checks"])


def test_removing_risks_fails_the_check(pack):
    rows = list(csv.DictReader((pack / "risk_register.csv").open(encoding="utf-8")))[:6]
    with (pack / "risk_register.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    assert not check()["passed"]


def test_a_missing_document_fails_the_check(pack):
    (pack / "classification.md").unlink()
    assert not check()["passed"]


def test_candidate_notice_matches_what_the_interview_page_shows():
    notice = (ROOT / "governance" / "candidate_notice.md")
    if not notice.exists():
        pytest.skip("governance pack not built")
    from app.web.interview import NOTICE
    assert NOTICE in notice.read_text(encoding="utf-8")
