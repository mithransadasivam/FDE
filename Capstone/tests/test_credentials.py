"""BR-20: certifications are checked against a (fictional) register and overlapping job dates are flagged, for a person to check; no score changes."""
import json
from datetime import date

from app.credentials import MIN_OVERLAP_MONTHS, check_certifications, credential_checks, load_register, overlapping_jobs
from app.models import Candidate
from tests.test_interview import shortlisted, token  # noqa: F401

TODAY = date(2026, 10, 15)


def test_the_register_is_labelled_fictional_and_lists_the_certifications_on_the_cvs():
    raw = json.loads(open("app/certification_register.json", encoding="utf-8").read())
    assert "FICTIONAL" in raw["about"] and len(load_register()) >= 10
    names = {c["name"] for c in load_register()}
    for cert in ("Certified Kubernetes Administrator", "ITIL 4 Foundation", "CompTIA Network+", "Microsoft Azure Fundamentals (AZ-900)"):
        assert cert in names


def test_a_known_certification_matches_by_name_or_short_name_and_an_unknown_one_is_flagged():
    out = {c["certification"]: c for c in check_certifications(["Certified Kubernetes Administrator", "cka", "Certified Quantum Cloud Architect Master"])}
    assert out["Certified Kubernetes Administrator"]["in_register"] and out["cka"]["in_register"] and "Cloud Native" in out["cka"]["issuer"]
    assert not out["Certified Quantum Cloud Architect Master"]["in_register"] and out["Certified Quantum Cloud Architect Master"]["issuer"] is None
    assert check_certifications(None) == []


def test_overlapping_jobs_at_different_employers_are_flagged_and_a_normal_handover_is_not():
    jobs = ["Engineer, Acme (Jan 2020 to Dec 2022)", "Consultant, Beta Ltd (Jun 2021 to Oct 2022)", "Analyst, Gamma (Nov 2022 to Mar 2023)"]
    o = overlapping_jobs(jobs, TODAY)
    assert len(o) == 1 and "Acme" in o[0]["first"] and "Beta" in o[0]["second"] and o[0]["months_overlapping"] >= 16  # Gamma overlaps Acme by one month: a handover
    assert overlapping_jobs(["Engineer, Acme (Jan 2020 to Dec 2022)", "Lead, Acme (Jan 2021 to Present)"], TODAY) == []  # the same employer (a promotion) is not an overlap
    assert MIN_OVERLAP_MONTHS == 2 and overlapping_jobs(["not a job line"], TODAY) == [] and overlapping_jobs(None) == []


def test_the_checks_make_sentences_for_a_person_and_say_when_there_is_nothing():
    clean = credential_checks({"certifications": {"value": ["ITIL 4 Foundation"]}, "jobs": {"value": ["Engineer, Acme (Jan 2020 to Dec 2022)"]}})
    assert clean["needs_review"] is False and clean["items"] == []
    odd = credential_checks({"certifications": {"value": ["Made Up Certificate"]}, "jobs": {"value": ["A, X (Jan 2020 to Dec 2022)", "B, Y (Jan 2021 to Dec 2022)"]}})
    assert odd["needs_review"] and len(odd["items"]) == 2 and "not in the certification register" in odd["items"][0] and "overlap by" in odd["items"][1]
    assert credential_checks(None)["needs_review"] is False


def test_the_candidate_page_shows_the_checks_and_a_flag_changes_no_score(shortlisted, db):
    from app.models_ext import ItemScoreRow

    before = [(r.skill, r.score) for r in db.query(ItemScoreRow).filter_by(candidate_id=1).order_by(ItemScoreRow.id)]
    cand = db.get(Candidate, 1)
    prof = dict(cand.profile)
    prof["certifications"] = {**prof["certifications"], "value": ["Made Up Certificate", "ITIL 4 Foundation"]}
    cand.profile = prof
    db.commit()
    html = shortlisted.rc.get("/candidates/1").text
    assert 'data-testid="credential-checks"' in html and "not in the register" in html and "in the register" in html and "for a person to check" in html
    assert "credential check" in shortlisted.rc.get("/candidates/1/scorecard").text
    db.expire_all()
    assert [(r.skill, r.score) for r in db.query(ItemScoreRow).filter_by(candidate_id=1).order_by(ItemScoreRow.id)] == before  # a flag changes no score
    assert db.get(Candidate, 1).stage == "SHORTLISTED"  # and moves nobody
