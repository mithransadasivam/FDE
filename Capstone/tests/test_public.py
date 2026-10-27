import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.models import Candidate, DecisionLog
from scripts.create_users import DEMO_PASSWORD, create_users
from tests.conftest import CVS, VOICE


@pytest.fixture
def staff(db):
    create_users(db)
    with TestClient(app, follow_redirects=False) as c:
        c.post("/login", data={"email": "hm@example.com", "password": DEMO_PASSWORD})
        yield c


@pytest.fixture
def published(staff):
    staff.post("/requisitions", data={"title": "Cloud Support Engineer"},
               files={"audio": ("REQ_cloud_support_engineer.wav", (VOICE / "REQ_cloud_support_engineer.wav").read_bytes(), "audio/wav")})
    staff.post("/requisitions/1/generate")
    staff.post("/requisitions/1/approve", data={"comment": "ok"})
    staff.post("/requisitions/1/publish")


@pytest.fixture
def visitor(published):
    """A signed-out candidate's browser."""
    with TestClient(app, follow_redirects=False) as c:
        yield c


def apply(client, name="C-001_cv.pdf", data=None, consent="yes", job=1):
    data = (CVS / "C-001_cv.pdf").read_bytes() if data is None else data
    form = {"consent": consent} if consent else {}
    return client.post(f"/jobs/{job}/apply", data=form, files={"cv": (name, data, "application/octet-stream")})


def test_jobs_list_and_job_page_need_no_sign_in_and_show_the_notice(visitor):
    assert "Cloud Support Engineer" in visitor.get("/jobs").text
    html = visitor.get("/jobs/1").text
    assert "How we use AI" in html and "ask for an interview with a person" in html
    assert f"{get_settings().retention_days} days" in html
    assert "Essential" in html and "Linux troubleshooting" in html


def test_unpublished_job_is_not_visible(staff):
    staff.post("/requisitions", data={"title": "x"},
               files={"audio": ("REQ_data_analyst.wav", (VOICE / "REQ_data_analyst.wav").read_bytes(), "audio/wav")})
    with TestClient(app, follow_redirects=False) as c:
        assert c.get("/jobs/1").status_code == 404
        assert "Data" not in c.get("/jobs").text
        assert apply(c).status_code == 404


def test_no_consent_is_refused_on_the_server(visitor, db):
    r = apply(visitor, consent="")
    assert r.status_code == 400 and "tick the box" in r.text
    assert apply(visitor, consent="no").status_code == 400
    assert db.query(Candidate).count() == 0


def test_exe_is_refused(visitor, db):
    r = apply(visitor, name="virus.exe", data=b"MZ")
    assert r.status_code == 400 and "File type .exe is not accepted" in r.text
    assert db.query(Candidate).count() == 0


def test_cv_over_5mb_refused(visitor):
    assert "larger than 5 MB" in apply(visitor, data=b"0" * (5 * 1024 * 1024 + 1)).text


def test_valid_application_creates_candidate_token_and_log(visitor, db):
    r = apply(visitor)
    assert r.status_code == 303
    cand = db.query(Candidate).one()
    assert cand.stage in ("APPLIED", "EXTRACTED", "REVIEW") and cand.consent_ai is True
    assert cand.cv_format == "pdf" and cand.cv_name == "C-001_cv.pdf" and len(cand.access_token) >= 30
    assert r.headers["location"] == f"/applied/{cand.access_token}"
    assert f"/me/{cand.access_token}" in visitor.get(r.headers["location"]).text
    assert "Your application" in visitor.get(f"/me/{cand.access_token}").text
    assert "applied, consent to AI given" in [e.action for e in db.query(DecisionLog)]


def test_tokens_are_unique_and_unknown_token_is_404(visitor, db):
    apply(visitor)
    apply(visitor)
    tokens = {c.access_token for c in db.query(Candidate)}
    assert len(tokens) == 2
    assert visitor.get("/me/not-a-real-token").status_code == 404


def test_formats_follow_the_extension(visitor, db):
    for name in ("a.docx", "b.jpg", "c.png", "d.jpeg"):
        apply(visitor, name=name, data=b"data")
    assert [c.cv_format for c in db.query(Candidate).order_by(Candidate.id)] == ["docx", "scan", "screenshot", "scan"]
