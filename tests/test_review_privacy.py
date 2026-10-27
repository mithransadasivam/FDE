import pytest
from fastapi.testclient import TestClient

from app.agents.document import extract_profile
from app.main import app
from app.models import Candidate, DecisionLog, ReviewItem
from app.privacy import HIDDEN, identity_leaks, make_blind
from app.schemas import BlindCandidate
from scripts.create_users import DEMO_PASSWORD, create_users
from tests.conftest import CVS, VOICE

FILES = ["C-001_cv.pdf", "C-004_cv.docx", "C-003_cv.jpg", "C-010_cv.png"]


def candidate_from(file, cid=1):
    p = extract_profile(CVS / file)
    return Candidate(id=cid, requisition_id=1, cv_path=str(CVS / file), cv_name=file, cv_format="pdf",
                     access_token=f"t{cid}", profile=p.model_dump(), stage="EXTRACTED")


# ---- make_blind and identity_leaks ----------------------------------------------------------------------------------
@pytest.mark.parametrize("file", FILES)
def test_zero_identity_leaks_for_each_format(file):
    cand = candidate_from(file)
    blind = make_blind(cand)
    assert identity_leaks(blind, cand) == []
    dump = blind.model_dump_json().lower()
    for field in ("name", "email", "phone", "address", "date_of_birth"):
        value = cand.profile[field]["value"]
        if value:
            assert value.lower() not in dump


def test_blind_record_keeps_the_skills_and_experience():
    blind = make_blind(candidate_from("C-001_cv.pdf"))
    assert blind.current_title == "Cloud Support Engineer" and blind.years_experience == 8.0
    assert "Linux" in blind.skills and len(blind.jobs) == 4 and "ITIL 4 Foundation" in blind.certifications


def test_a_name_inside_another_field_is_hidden_including_its_parts():
    cand = candidate_from("C-001_cv.pdf")
    cand.profile["current_title"]["value"] = "Cloud Support Engineer at Amara"
    cand.profile["jobs"]["value"] = ["Engineer, Okafor Ltd (Jan 2020 to Jan 2021)"]
    cand.profile["skills"]["value"] = ["Linux", "amara.okafor@example.com", "+44 7700 900100", "63 Kestrel Drive"]
    blind = make_blind(cand)
    assert blind.current_title == f"Cloud Support Engineer at {HIDDEN}"
    assert blind.jobs == [f"Engineer, {HIDDEN} Ltd (Jan 2020 to Jan 2021)"]
    assert blind.skills == ["Linux", HIDDEN, HIDDEN, HIDDEN]
    assert identity_leaks(blind, cand) == []


def test_word_boundaries_do_not_damage_ordinary_words():
    cand = candidate_from("C-001_cv.pdf")
    cand.profile["name"]["value"] = "Li Wu"
    cand.profile["skills"]["value"] = ["Linux", "Wuhan networking"]
    blind = make_blind(cand)
    assert blind.skills == ["Linux", "Wuhan networking"]


def test_identity_leaks_catches_a_leak():
    cand = candidate_from("C-001_cv.pdf")
    leaky = BlindCandidate(candidate_id=1, current_title="Amara Okafor", skills=["call +44 7700 900100"])
    leaks = identity_leaks(leaky, cand)
    assert "Amara Okafor" in leaks and any("7700" in x for x in leaks)


# ---- the web pages -----------------------------------------------------------------------------------------------------
@pytest.fixture
def clients(db):
    create_users(db)
    hm, rc, visitor = (TestClient(app, follow_redirects=False) for _ in range(3))
    for c in (hm, rc, visitor):
        c.__enter__()
    hm.post("/login", data={"email": "hm@example.com", "password": DEMO_PASSWORD})
    rc.post("/login", data={"email": "recruiter@example.com", "password": DEMO_PASSWORD})
    hm.post("/requisitions", data={"title": "Cloud Support Engineer"},
            files={"audio": ("REQ_cloud_support_engineer.wav", (VOICE / "REQ_cloud_support_engineer.wav").read_bytes(), "audio/wav")})
    hm.post("/requisitions/1/generate")
    hm.post("/requisitions/1/approve", data={"comment": "ok"})
    hm.post("/requisitions/1/publish")
    yield hm, rc, visitor
    for c in (hm, rc, visitor):
        c.__exit__(None, None, None)


def apply(visitor, name):
    visitor.post("/jobs/1/apply", data={"consent": "yes"}, files={"cv": (name, (CVS / name).read_bytes(), "application/octet-stream")})


def test_hiring_manager_never_sees_an_email_name_or_phone(clients):
    hm, rc, visitor = clients
    for f in FILES:
        apply(visitor, f)
    for url in ("/candidates", "/candidates?blind=0", "/candidates/1", "/candidates/1?blind=0", "/candidates/3?blind=0"):
        html = hm.get(url).text
        assert "@example.com" not in html and "+44" not in html
        for name in ("Amara", "Okafor", "Chen", "Lindqvist", "Jonas", "Kowalski", "Daniela"):
            assert name not in html
        assert "Blind view" in html
    assert "Candidate #1" in hm.get("/candidates").text
    assert hm.get("/candidates/1/cv").status_code == 403  # the original CV shows identity


def test_recruiter_sees_identity_unless_blind_view_is_switched_on(clients):
    hm, rc, visitor = clients
    apply(visitor, "C-001_cv.pdf")
    assert "Amara Okafor" in rc.get("/candidates").text
    blind = rc.get("/candidates?blind=1").text
    assert "Amara" not in blind and "Candidate #1" in blind
    page = rc.get("/candidates/1").text
    assert "Blind record" in page and "Extracted fields" in page and "amara.okafor@example.com" in page
    assert "amara.okafor" not in rc.get("/candidates/1?blind=1").text
    assert rc.get("/candidates/1/cv").status_code == 200


def test_review_queue_is_recruiter_only(clients):
    hm, rc, _ = clients
    assert hm.get("/review").status_code == 403
    assert rc.get("/review").status_code == 200
    assert hm.post("/review/1/save", data={}).status_code == 403


def test_review_queue_lists_the_unsure_fields(clients, db):
    hm, rc, visitor = clients
    apply(visitor, "C-001_cv.pdf")
    apply(visitor, "C-003_cv.jpg")
    html = rc.get("/review").text
    assert "Candidate #2" in html and "Candidate #1" not in html
    assert html.count('name="value_') == 3 and 'name="value_phone"' in html and "3 fields" in html


def test_correcting_a_field_saves_it_resolves_it_and_logs_before_and_after(clients, db):
    hm, rc, visitor = clients
    apply(visitor, "C-003_cv.jpg")
    rc.post("/review/1/save", data={"value_phone": "+44 7700 900999", "value_jobs": db.query(ReviewItem).filter_by(field="jobs").one().value,
                                    "value_years_experience": "1.0"})
    db.expire_all()
    cand = db.get(Candidate, 1)
    assert cand.profile["phone"] == {"value": "+44 7700 900999", "confidence": 1.0}
    assert cand.profile["jobs"]["confidence"] == 1.0
    assert db.query(ReviewItem).filter_by(resolved=False).count() == 0
    entry = db.query(DecisionLog).filter_by(action="corrected phone").one()
    assert entry.actor == "recruiter@example.com"
    assert entry.evidence == {"before": "+44 7700 900102", "after": "+44 7700 900999"}


def test_changing_the_jobs_recalculates_the_years(clients, db):
    hm, rc, visitor = clients
    apply(visitor, "C-003_cv.jpg")
    rc.post("/review/1/save", data={"value_phone": "+44 7700 900102",
                                    "value_jobs": "DevOps Engineer, Larkspur Telecom (Oct 2023 to Oct 2025); Analyst, X (Jan 2025 to Present)",
                                    "value_years_experience": "1.0"})
    db.expire_all()
    p = db.get(Candidate, 1).profile
    assert p["years_experience"]["value"] == 3.0 and p["years_experience"]["confidence"] == 1.0  # Oct 2023 to Oct 2026
    assert len(p["jobs"]["value"]) == 2
    e = db.query(DecisionLog).filter_by(action="corrected years_experience").one()
    assert e.evidence["before"] == "1.0" and e.evidence["after"] == "3.0"


def test_confirm_needs_everything_checked_then_moves_to_extracted(clients, db):
    hm, rc, visitor = clients
    apply(visitor, "C-003_cv.jpg")
    rc.post("/review/1/confirm")
    assert db.get(Candidate, 1).stage == "REVIEW"  # refused: fields still to check
    values = {f"value_{i.field}": i.value for i in db.query(ReviewItem)}
    rc.post("/review/1/save", data=values)
    assert "Nothing left to check" in rc.get("/review").text
    rc.post("/review/1/confirm")
    db.expire_all()
    assert db.get(Candidate, 1).stage == "EXTRACTED"
    assert db.query(DecisionLog).filter_by(action="move REVIEW -> EXTRACTED").one().actor == "recruiter@example.com"


def test_bad_years_value_is_refused_without_saving(clients, db):
    hm, rc, visitor = clients
    apply(visitor, "C-003_cv.jpg")
    rc.post("/review/1/save", data={"value_years_experience": "lots"})
    assert db.query(ReviewItem).filter_by(resolved=False).count() == 3
