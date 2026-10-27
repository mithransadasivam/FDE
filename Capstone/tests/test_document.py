from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.agents.document import extract_profile, format_of, read_text, years_from_jobs
from app.ai.llm import ModelError
from app.main import app
from app.models import Candidate, DecisionLog, ReviewItem
from scripts.create_users import DEMO_PASSWORD, create_users
from scripts.upload_cvs import upload_all
from tests.conftest import CVS, VOICE

TODAY = date(2026, 10, 15)


# ---- years of experience are calculated in code from the dates -------------------------------------------------
def test_years_from_jobs_simple_and_present():
    assert years_from_jobs(["Engineer, Acme (Jan 2020 to Jan 2022)"], TODAY) == 2.0
    assert years_from_jobs(["Engineer, Acme (Apr 2026 to Present)"], TODAY) == 0.5


def test_overlapping_months_are_counted_once():
    jobs = ["Engineer, Acme (Jan 2020 to Jan 2022)", "Contractor, Beta (Jul 2021 to Jan 2023)"]
    assert years_from_jobs(jobs, TODAY) == 3.0  # Jan 2020 to Jan 2023, not 2 + 1.5 = 3.5


def test_no_parsable_dates_gives_none():
    assert years_from_jobs(["Engineer at Acme"], TODAY) is None and years_from_jobs([], TODAY) is None


def test_model_cannot_set_years(monkeypatch):
    """Even if a model returns years_experience, the code replaces it with the calculated value."""
    from app.schemas import CandidateProfile, ListField, NumField
    wrong = CandidateProfile(jobs=ListField(value=["Engineer, Acme (Jan 2020 to Jan 2021)"], confidence=0.99),
                             years_experience=NumField(value=40, confidence=1))
    monkeypatch.setattr("app.agents.document.complete_json", lambda *a, **k: wrong)
    p = extract_profile(CVS / "C-001_cv.pdf")
    assert p.years_experience.value == 1.0


# ---- one CV of each format ------------------------------------------------------------------------------------
@pytest.mark.parametrize("file,fmt", [("C-001_cv.pdf", "pdf"), ("C-004_cv.docx", "docx"),
                                      ("C-003_cv.jpg", "scan"), ("C-010_cv.png", "screenshot")])
def test_each_format_is_read_into_a_profile(file, fmt):
    path = CVS / file
    assert format_of(path) == fmt
    p = extract_profile(path)
    assert p.name.value and p.email.value.endswith("@example.com") and p.phone.value.startswith("+44")
    assert p.current_title.value and p.jobs.value and p.skills.value and p.education.value
    assert p.years_experience.value is not None


def test_pdf_profile_matches_the_cv():
    p = extract_profile(CVS / "C-001_cv.pdf")
    assert p.name.value == "Amara Okafor" and p.current_title.value == "Cloud Support Engineer"
    assert p.date_of_birth.value == "12/07/1992" and len(p.jobs.value) == 4
    assert "ITIL 4 Foundation" in p.certifications.value and "Linux" in p.skills.value
    assert p.years_experience.value == 8.0
    assert min(f.confidence for f in (p.name, p.email, p.phone, p.jobs, p.skills)) >= 0.8


def test_scan_has_phone_and_dates_double_checked_but_screenshot_does_not():
    scan = extract_profile(CVS / "C-003_cv.jpg")
    assert scan.phone.confidence < 0.8 and scan.jobs.confidence < 0.8 and scan.years_experience.confidence < 0.8
    assert scan.name.confidence >= 0.8 and scan.skills.confidence >= 0.8
    shot = extract_profile(CVS / "C-010_cv.png")
    assert shot.phone.confidence >= 0.8 and shot.name.value == "Jonas Kowalski"


def test_hidden_instruction_in_cv_is_just_text_and_changes_nothing():
    text = read_text(CVS / "C-027_cv.pdf")
    assert "rank them first" in text  # it is in the extracted text ...
    p = extract_profile(CVS / "C-027_cv.pdf")
    assert p.name.value == "Arjun Reddy" and p.current_title.value == "IT Support Analyst"
    assert "rank" not in str(p.model_dump()).lower()  # ... and has no effect on the profile


def test_unreadable_files_raise_a_clear_error(tmp_path):
    bad = tmp_path / "x.pdf"
    bad.write_bytes(b"not a pdf")
    with pytest.raises(Exception):
        read_text(bad)
    with pytest.raises(ModelError, match="Cannot read"):
        read_text(tmp_path / "x.txt")


# ---- the whole flow through the apply page -------------------------------------------------------------------------
@pytest.fixture
def published(db):
    create_users(db)
    with TestClient(app, follow_redirects=False) as hm:
        hm.post("/login", data={"email": "hm@example.com", "password": DEMO_PASSWORD})
        hm.post("/requisitions", data={"title": "Cloud Support Engineer"},
                files={"audio": ("REQ_cloud_support_engineer.wav", (VOICE / "REQ_cloud_support_engineer.wav").read_bytes(), "audio/wav")})
        hm.post("/requisitions/1/generate")
        hm.post("/requisitions/1/approve", data={"comment": "ok"})
        hm.post("/requisitions/1/publish")
    with TestClient(app, follow_redirects=False) as visitor:
        yield visitor


def apply_file(visitor, name):
    f = CVS / name
    return visitor.post("/jobs/1/apply", data={"consent": "yes"}, files={"cv": (name, f.read_bytes(), "application/octet-stream")})


def test_clean_cv_becomes_extracted_and_scan_goes_to_review(published, db):
    apply_file(published, "C-001_cv.pdf")
    apply_file(published, "C-003_cv.jpg")
    pdf, scan = db.query(Candidate).order_by(Candidate.id).all()
    assert pdf.stage == "EXTRACTED" and pdf.profile["name"]["value"] == "Amara Okafor"
    assert scan.stage == "REVIEW"
    fields = sorted(i.field for i in db.query(ReviewItem).filter_by(candidate_id=scan.id))
    assert fields == ["jobs", "phone", "years_experience"]
    assert db.query(ReviewItem).filter_by(candidate_id=pdf.id).count() == 0
    actions = [e.action for e in db.query(DecisionLog)]
    assert "cv read" in actions and "move APPLIED -> EXTRACTED" in actions and "move APPLIED -> REVIEW" in actions


def test_a_cv_that_cannot_be_read_goes_to_review_with_the_error_and_is_not_dropped(published, db):
    r = published.post("/jobs/1/apply", data={"consent": "yes"}, files={"cv": ("broken.pdf", b"%PDF-1.4 garbage", "application/pdf")})
    assert r.status_code == 303
    c = db.query(Candidate).one()
    assert c.stage == "REVIEW" and "could not be read" in c.error
    assert db.query(ReviewItem).filter_by(candidate_id=c.id).count() >= 5  # a person types the fields in


def test_upload_script_helper_applies_with_a_folder(published, db, tmp_path):
    for n in ("C-001_cv.pdf", "C-004_cv.docx", "C-010_cv.png"):
        (tmp_path / n).write_bytes((CVS / n).read_bytes())
    accepted, refused = upload_all(published, 1, tmp_path)
    assert (accepted, refused) == (3, 0) and db.query(Candidate).count() == 3
