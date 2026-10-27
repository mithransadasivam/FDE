import re
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import Candidate, DecisionLog
from app.schemas import Stage
from app.supervisor import ALLOWED, PERSON, SYSTEM, MoveRefused, move
from scripts.create_users import DEMO_PASSWORD, create_users
from tests.conftest import CVS, VOICE


@pytest.fixture
def cand(db):
    c = Candidate(requisition_id=1, cv_path="x", cv_name="x.pdf", cv_format="pdf", access_token="t", stage="APPLIED")
    db.add(c)
    db.commit()
    return c


# ---- the rules -------------------------------------------------------------------------------------------------------
def test_applied_to_shortlisted_is_refused_and_says_what_is_allowed(db, cand):
    with pytest.raises(MoveRefused) as e:
        move(db, cand, Stage.SHORTLISTED, "recruiter@example.com", "because")
    assert "not allowed" in str(e.value) and "EXTRACTED, REVIEW, WITHDRAWN" in str(e.value)
    assert cand.stage == "APPLIED"


def test_system_can_read_and_screen_but_cannot_shortlist(db, cand):
    move(db, cand, Stage.EXTRACTED, SYSTEM)
    move(db, cand, Stage.SCREENED, SYSTEM)
    with pytest.raises(MoveRefused, match="only a person can make it"):
        move(db, cand, Stage.SHORTLISTED, SYSTEM, "I think they are great")
    assert cand.stage == "SCREENED"


def test_a_persons_decision_needs_a_reason(db, cand):
    move(db, cand, Stage.REVIEW, SYSTEM)
    for blank in ("", "   "):
        with pytest.raises(MoveRefused, match="needs a reason"):
            move(db, cand, Stage.EXTRACTED, "recruiter@example.com", blank)
    move(db, cand, Stage.EXTRACTED, "recruiter@example.com", "checked every field")
    assert cand.stage == "EXTRACTED"


def test_every_move_is_logged_with_who_and_why(db, cand):
    move(db, cand, Stage.EXTRACTED, SYSTEM, "read ok")
    move(db, cand, Stage.WITHDRAWN, "recruiter@example.com", "candidate asked to withdraw", evidence={"mail": 1})
    db.commit()
    rows = db.query(DecisionLog).order_by(DecisionLog.id).all()
    assert [(r.actor, r.action) for r in rows] == [("system", "move APPLIED -> EXTRACTED"),
                                                  ("recruiter@example.com", "move EXTRACTED -> WITHDRAWN")]
    assert rows[1].reason == "candidate asked to withdraw" and rows[1].evidence == {"mail": 1}


def test_nothing_leaves_withdrawn_and_unknown_stage_is_refused(db, cand):
    move(db, cand, Stage.WITHDRAWN, "r@example.com", "withdrawn")
    with pytest.raises(MoveRefused, match="process has ended"):
        move(db, cand, Stage.EXTRACTED, "r@example.com", "oops")
    with pytest.raises(MoveRefused, match="not a stage"):
        move(db, cand, "HIRED", "r@example.com", "x")


def test_table_every_decision_is_a_persons_and_only_early_steps_are_automatic():
    automatic = {(f, t) for f, moves in ALLOWED.items() for t, who in moves.items() if who == SYSTEM}
    assert automatic == {(Stage.APPLIED, Stage.EXTRACTED), (Stage.APPLIED, Stage.REVIEW), (Stage.EXTRACTED, Stage.SCREENED)}
    for frm, moves in ALLOWED.items():
        assert moves.get(Stage.WITHDRAWN, PERSON) == PERSON
    assert ALLOWED[Stage.SCREENED][Stage.SHORTLISTED] == PERSON and ALLOWED[Stage.REVIEW][Stage.EXTRACTED] == PERSON


def test_no_code_outside_the_supervisor_sets_the_stage_directly():
    """Rule 1 depends on move() being the only way to change a stage."""
    offenders = []
    for path in Path("app").rglob("*.py"):
        if path.name == "supervisor.py":
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\.stage\s*=[^=]", line):
                offenders.append(f"{path}:{n}: {line.strip()}")
    assert offenders == []


# ---- the pipeline board -----------------------------------------------------------------------------------------------
@pytest.fixture
def board(db):
    create_users(db)
    hm, rc, visitor = (TestClient(app, follow_redirects=False) for _ in range(3))
    for c in (hm, rc, visitor):
        c.__enter__()
    hm.post("/login", data={"email": "hm@example.com", "password": DEMO_PASSWORD})
    rc.post("/login", data={"email": "recruiter@example.com", "password": DEMO_PASSWORD})
    hm.post("/requisitions", data={"title": "x"},
            files={"audio": ("REQ_cloud_support_engineer.wav", (VOICE / "REQ_cloud_support_engineer.wav").read_bytes(), "audio/wav")})
    hm.post("/requisitions/1/generate")
    hm.post("/requisitions/1/approve", data={})
    hm.post("/requisitions/1/publish")
    for name in ("C-001_cv.pdf", "C-003_cv.jpg"):
        visitor.post("/jobs/1/apply", data={"consent": "yes"}, files={"cv": (name, (CVS / name).read_bytes(), "application/octet-stream")})
    yield hm, rc
    for c in (hm, rc, visitor):
        c.__exit__(None, None, None)


def test_board_has_a_column_per_stage_with_candidates_in_the_right_ones(board):
    hm, rc = board
    html = rc.get("/pipeline").text
    for s in Stage:
        assert f"{s.value} <span" in html
    cols = {m.group(1): m.group(2) for m in re.finditer(r"<h3>(\w+) <span class=\"badge\">(\d+)</span>", html)}
    assert cols["EXTRACTED"] == "1" and cols["REVIEW"] == "1" and cols["APPLIED"] == "0" and cols["SHORTLISTED"] == "0"


def test_forbidden_move_is_refused_with_the_message_on_the_page(board, db):
    hm, rc = board
    rc.post("/pipeline/move", data={"candidate_id": 1, "to": "SHORTLISTED", "reason": "looks good"})
    html = rc.get("/pipeline").text
    assert "Refused" in html and "From EXTRACTED a candidate can go to: SCREENED, WITHDRAWN" in html
    assert db.get(Candidate, 1).stage == "EXTRACTED"


def test_allowed_person_move_works_and_is_logged(board, db):
    hm, rc = board
    rc.post("/pipeline/move", data={"candidate_id": 1, "to": "WITHDRAWN", "reason": "withdrew their application"})
    db.expire_all()
    assert db.get(Candidate, 1).stage == "WITHDRAWN"
    assert db.query(DecisionLog).filter_by(action="move EXTRACTED -> WITHDRAWN").one().reason == "withdrew their application"
    rc.post("/pipeline/move", data={"candidate_id": 2, "to": "EXTRACTED", "reason": ""})
    assert db.get(Candidate, 2).stage == "REVIEW"  # refused: no reason


def test_hiring_manager_sees_a_blind_board_and_cannot_move_candidates(board):
    hm, rc = board
    html = hm.get("/pipeline?blind=0").text
    assert "Amara" not in html and "@example.com" not in html and "Blind view" in html
    assert "Move a candidate" not in html
    assert hm.post("/pipeline/move", data={"candidate_id": 1, "to": "WITHDRAWN", "reason": "x"}).status_code == 403
    assert "Amara Okafor" in rc.get("/pipeline").text


# ---- the whole day in one command ---------------------------------------------------------------------------------------
def test_day1_demo_runs_end_to_end_on_all_52_cvs(monkeypatch, capsys, db):
    from scripts import day1_demo
    monkeypatch.setattr(sys, "argv", ["day1_demo", "--reset"])
    assert day1_demo.main() == 0
    out = capsys.readouterr().out
    assert "REQ-001 PUBLISHED: 8 skills, weights 100" in out
    assert "Wording flags: young and energetic, native English speaker" in out
    assert "Applications: 52 (52 accepted, 0 refused) stages: {'EXTRACTED': 44, 'REVIEW': 8}" in out
    assert "Fields in the review queue: 24 identity leaks in blind records: 0" in out
    assert "Forbidden move refused" in out and "Day 1 demo complete." in out


def test_demo_also_flags_the_duplicate_and_publishes_the_second_role(monkeypatch, capsys, db):
    from scripts import day1_demo
    monkeypatch.setattr(sys, "argv", ["day1_demo", "--reset"])
    assert day1_demo.main() == 0
    out = capsys.readouterr().out
    assert "C-015_cv.pdf and C-048_cv.png" in out
    assert "REQ-002 PUBLISHED: 7 skills, weights 100; wording flags: He will, rockstar" in out
