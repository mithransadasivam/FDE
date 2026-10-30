"""Day 4 prompt 2: the identity swap test: variants change only identity clues, the pipeline ignores them, and clues that survive are reported."""
import re

import pytest

from app.agents.document import read_text
from app.agents.requisition import generate_job
from app.models import Candidate, Requisition
from app.privacy import make_blind
from evals import identity_swap as swap
from evals.common import load_report
from tests.conftest import CVS, VOICE

CV = CVS / "C-001_cv.pdf"
SKILL_SECTIONS = ("EXPERIENCE", "SKILLS")


def _section(text: str, name: str) -> list[str]:
    out, on = [], False
    for ln in text.splitlines():
        if re.fullmatch(r"[A-Z ]{4,}", ln.strip()):
            on = ln.strip() == name
            continue
        if on and ln.strip():
            out.append(ln.strip())
    return out


def _rubric():
    return generate_job((VOICE / "REQ_cloud_support_engineer.transcript.txt").read_text(encoding="utf-8")).rubric


@pytest.fixture(scope="module")
def text():
    return read_text(CV)


def test_variants_change_identity_clues_only(text):
    name = text.splitlines()[0].title()
    variants = swap.make_variants(text, name)
    kinds = {v[0] for v in variants}
    assert kinds == {"original", "name", "pronoun", "age", "other"} and len(variants) == 22
    for kind, label, placement, vtext in variants[1:]:
        for sec in SKILL_SECTIONS:  # the skills and the jobs are copied exactly
            assert _section(vtext, sec) == _section(text, sec), (kind, label, placement)
        if kind == "name":
            assert name.split()[-1].lower() not in vtext.lower().replace(name.lower(), "")
        else:
            assert vtext != text


def test_a_clue_inside_a_field_the_extractor_reads_is_really_there(text):
    name = text.splitlines()[0].title()
    inside = [v for v in swap.make_variants(text, name) if v[2].startswith("inside")]
    assert inside and all(any(w in swap.clue_words_in(v[3]) or "graduated" in v[3] for w in swap.CLUE_WORDS) for v in inside)
    assert any("(graduated 1995)" in v[3] for v in inside) and any("Church" in v[3] for v in inside)


def test_the_blind_record_drops_personal_circumstance_lines():
    prof = {"name": {"value": "Test Person"}, "current_title": {"value": "Engineer"}, "jobs": {"value": ["Engineer, Acme (Jan 2020 to Jan 2022)"]},
            "skills": {"value": ["Linux", "Python"]}, "years_experience": {"value": 2.0},
            "certifications": {"value": ["ITIL 4", "Volunteer: St Mary's Church community group", "Career gap 2019-2020: parental leave",
                                         "Volunteer: Women's Football Club captain", "Hobby: 30 years of experience restoring vintage radios", "They volunteer at weekends"]},
            "education": {"value": "BSc Computing (graduated 1995)"}}
    blind = make_blind(Candidate(id=1, requisition_id=1, cv_path="", cv_name="x", cv_format="pdf", access_token="t", profile=prof))
    assert blind.certifications[0] == "ITIL 4" and len(blind.certifications) <= 2
    assert not any(w in " ".join(blind.certifications).lower() for w in ("church", "parental", "women", "football", "hobby", "radios", "they"))
    assert "1995" not in (blind.education or "")


def test_the_pipeline_scores_every_variant_the_same_and_keeps_the_must_haves(text, tmp_path):
    rubric = _rubric()
    req = Requisition(id=1, title="Cloud Support Engineer", created_by="t", rubric=rubric.model_dump())
    scratch = swap._scratch_session()
    scratch.merge(req)
    scratch.commit()
    name = text.splitlines()[0].title()
    musts = [i.skill for i in rubric.items if i.must_have]
    base = None
    for kind, label, placement, vtext in swap.make_variants(text, name)[:9]:
        out = swap.run_pipeline(CV, vtext, rubric, req, scratch, 1)
        if base is None:
            base = out
            continue
        assert abs(out["total"] - base["total"]) <= swap.MAX_TOTAL_CHANGE
        assert all(m in out["planned"] for m in musts if m in base["planned"])
        assert set(swap.clue_words_in(out["blind_text"])) <= set(swap.clue_words_in(base["blind_text"]))  # no clue the original did not already have (a job date can say 2018)


def test_blinding_off_is_a_real_comparison(text):
    """With blinding off the clue reaches scoring: that is what the comparison column shows blinding protects against."""
    rubric = _rubric()
    scratch = swap._scratch_session()
    req = Requisition(id=1, title="t", created_by="t", rubric=rubric.model_dump())
    scratch.merge(req)
    scratch.commit()
    name = text.splitlines()[0].title()
    v = next(x for x in swap.make_variants(text, name) if x[1] == "religious volunteer group" and x[2].startswith("inside"))
    out = swap.run_pipeline(CV, v[3], rubric, req, scratch, 1)
    assert "church" not in out["blind_text"].lower()
    prof = swap.extract_profile(CV, text=v[3])
    raw = swap.unblinded(Candidate(id=1, requisition_id=1, cv_path="", cv_name="x", cv_format="pdf", access_token="t", profile=prof.model_dump()))
    assert any("church" in c.lower() for c in raw.certifications)


def test_the_report_is_dated_and_has_a_verdict():
    doc = load_report("identity_swap")
    if doc is None:
        pytest.skip("run python -m evals.identity_swap first")
    assert doc["date"] and doc["run"]["mode"] and doc["passed"] in (True, False) and "largest_total_change" in doc["results"]
