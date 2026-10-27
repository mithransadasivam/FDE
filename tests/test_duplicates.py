import pytest
from fastapi.testclient import TestClient

from app.duplicates import duplicate_map
from app.main import app
from app.models import Candidate, DecisionLog
from scripts.create_users import DEMO_PASSWORD, create_users
from tests.conftest import CVS, VOICE


def cand(cid, email, phone, req=1):
    p = {"email": {"value": email, "confidence": 1}, "phone": {"value": phone, "confidence": 1}}
    return Candidate(id=cid, requisition_id=req, cv_path="x", cv_name=f"{cid}.pdf", cv_format="pdf", access_token=f"t{cid}", profile=p)


def test_same_email_or_phone_is_flagged_both_ways(db):
    db.add_all([cand(1, "a@example.com", "+44 7700 900100"), cand(2, "A@Example.com", "+44 7700 900999"),
                cand(3, "c@example.com", "07700 900100"), cand(4, "d@example.com", "+44 7700 900444")])
    db.commit()
    assert duplicate_map(db) == {1: [2, 3], 2: [1], 3: [1]}


def test_the_same_person_on_a_different_job_is_not_a_duplicate(db):
    db.add_all([cand(1, "a@example.com", "+44 7700 900100", req=1), cand(2, "a@example.com", "+44 7700 900100", req=2)])
    db.commit()
    assert duplicate_map(db) == {}


def test_missing_fields_never_match(db):
    db.add_all([cand(1, None, None), cand(2, None, None)])
    db.commit()
    assert duplicate_map(db) == {}


@pytest.fixture
def clients(db):
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
    yield hm, rc, visitor
    for c in (hm, rc, visitor):
        c.__exit__(None, None, None)


def test_c048_is_flagged_as_the_same_person_as_c015_and_a_person_decides(clients, db):
    hm, rc, visitor = clients
    for name in ("C-015_cv.pdf", "C-048_cv.png"):  # the same person as a PDF and as a profile screenshot
        visitor.post("/jobs/1/apply", data={"consent": "yes"}, files={"cv": (name, (CVS / name).read_bytes(), "application/octet-stream")})
    assert db.query(DecisionLog).filter_by(action="possible duplicate").one().subject == "candidate:2"
    assert "duplicate of #1" in rc.get("/candidates").text and "duplicate of #2" in rc.get("/pipeline").text
    page = rc.get("/candidates/2").text
    assert "Possible duplicate" in page and "a person decides" in page
    assert "Possible duplicate" in hm.get("/candidates/2").text and "Withdraw this application" not in hm.get("/candidates/2").text
    assert db.get(Candidate, 2).stage in ("EXTRACTED", "REVIEW")  # flagged only: nothing was rejected or merged
    rc.post("/pipeline/move", data={"candidate_id": 2, "to": "WITHDRAWN", "reason": "Duplicate application of candidate #1"})
    db.expire_all()
    assert db.get(Candidate, 2).stage == "WITHDRAWN"
