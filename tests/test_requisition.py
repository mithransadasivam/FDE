import re

import pytest
from fastapi.testclient import TestClient

from app.agents.requisition import _fake, generate_job
from app.ai.llm import ModelError, complete_json
from app.main import app
from app.models import DecisionLog, Requisition
from app.schemas import JobDraft
from scripts.create_users import DEMO_PASSWORD, create_users
from tests.conftest import VOICE

NOTES = {n: (VOICE / f"REQ_{n}.transcript.txt").read_text(encoding="utf-8").strip()
         for n in ("cloud_support_engineer", "data_analyst", "platform_engineer")}


@pytest.mark.parametrize("name", list(NOTES))
def test_rubric_adds_to_100_and_every_skill_evidence_is_in_the_transcript(name):
    draft = generate_job(NOTES[name])
    assert draft.rubric.total == 100
    assert 5 <= len(draft.rubric.items) <= 10
    low = NOTES[name].lower()
    for item in draft.rubric.items:
        assert item.evidence_from_note.lower() in low
        assert item.weight <= 40


def test_cloud_support_note_gives_8_skills_with_the_expected_must_haves():
    draft = generate_job(NOTES["cloud_support_engineer"])
    assert len(draft.rubric.items) == 8
    assert {i.skill for i in draft.rubric.items if i.must_have} == {"Linux troubleshooting", "Cloud networking", "Incident handling"}
    assert draft.rubric.min_years == 2
    assert draft.job.title == "Cloud Support Engineer"


def test_job_text_contains_no_biased_wording():
    for note in NOTES.values():
        text = generate_job(note).job.as_text().lower()
        for bad in ("young", "energetic", "native", "rockstar", "he will", "she will"):
            assert bad not in text


def test_invented_skill_is_rejected(monkeypatch):
    """If the model invents a skill that is not in the transcript, code rejects the draft."""
    good = _fake(f"<transcript>\n{NOTES['cloud_support_engineer']}\n</transcript>")
    data = good.model_dump()
    data["rubric"]["items"][0]["skill"] = "Quantum computing"
    data["rubric"]["items"][0]["evidence_from_note"] = "quantum computing"
    monkeypatch.setattr("app.agents.requisition.complete_json", lambda *a, **k: JobDraft.model_validate(data))
    with pytest.raises(ModelError, match="Quantum computing"):
        generate_job(NOTES["cloud_support_engineer"])


def test_complete_json_fake_rejects_bad_shape():
    with pytest.raises(ModelError):
        complete_json("s", "u", JobDraft, fake=lambda u: {"job": {}, "rubric": {}})


def test_complete_json_retries_once_with_the_validation_error(monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "fake_models", False)
    monkeypatch.setattr(get_settings(), "openrouter_api_key", "test")
    replies = ['{"nope": 1}', _fake(f"<transcript>\n{NOTES['data_analyst']}\n</transcript>").model_dump_json()]
    seen = []

    def fake_call(model, messages, max_tokens=3000):
        seen.append(len(messages))
        return replies.pop(0)

    monkeypatch.setattr("app.ai.llm._call", fake_call)
    assert complete_json("sys", "user", JobDraft).rubric.total == 100
    assert seen == [2, 4]  # the second call carried the first reply and the error


def test_complete_json_gives_up_after_one_retry(monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "fake_models", False)
    monkeypatch.setattr("app.ai.llm._call", lambda *a, **k: "not json")
    with pytest.raises(ModelError, match="not valid after a retry"):
        complete_json("sys", "user", JobDraft)


@pytest.fixture
def hm(db):
    create_users(db)
    with TestClient(app, follow_redirects=False) as c:
        c.post("/login", data={"email": "hm@example.com", "password": DEMO_PASSWORD})
        yield c


def make_req(client, note="cloud_support_engineer"):
    client.post("/requisitions", data={"title": note}, files={"audio": (f"REQ_{note}.wav", (VOICE / f"REQ_{note}.wav").read_bytes(), "audio/wav")})


def test_generate_button_flow(hm, db):
    make_req(hm)
    assert hm.post("/requisitions/1/generate").status_code == 303
    req = db.get(Requisition, 1)
    assert req.status == "GENERATED" and len(req.rubric["items"]) == 8
    html = hm.get("/requisitions/1").text
    assert "Linux troubleshooting" in html and "&ldquo;Linux troubleshooting&rdquo;" in html
    assert re.search(r"<th>Total</th><th>100</th>", html)
    assert "draft generated" in [e.action for e in db.query(DecisionLog)]


def test_generate_refused_before_transcription(hm, db):
    make_req(hm, "cloud_support_engineer")
    req = db.get(Requisition, 1)
    req.status = "DRAFT"
    db.commit()
    hm.post("/requisitions/1/generate")
    assert db.get(Requisition, 1).status == "DRAFT"


def test_recruiter_cannot_generate(hm, db):
    make_req(hm)
    with TestClient(app, follow_redirects=False) as rc:
        rc.post("/login", data={"email": "recruiter@example.com", "password": DEMO_PASSWORD})
        assert rc.post("/requisitions/1/generate").status_code == 403


# ---- Prompt 8: biased-wording check -------------------------------------------------------------------
from app.agents.wording import check_requisition, check_wording  # noqa: E402


def phrases(text):
    return [f.phrase.lower() for f in check_wording(text)]


def test_cloud_support_note_is_flagged_for_young_and_native_speaker():
    flags = check_wording(NOTES["cloud_support_engineer"])
    assert [f.phrase.lower() for f in flags] == ["young and energetic", "native english speaker"]
    assert all(f.reason and f.suggestion for f in flags)


def test_data_analyst_note_flags_rockstar_and_he_will():
    assert phrases(NOTES["data_analyst"]) == ["he will", "rockstar"]


def test_platform_note_has_no_flags_and_neutral_text_gives_none():
    assert check_wording(NOTES["platform_engineer"]) == []
    assert check_wording("Strong Linux skills and clear writing. They will join the on-call rota.") == []


def test_each_phrase_once_longest_first():
    flags = check_wording("We want someone young and energetic. Young and energetic people thrive here.")
    assert [f.phrase.lower() for f in flags] == ["young and energetic"]  # not 'young' and 'energetic' separately
    assert len(check_wording("A ninja. Another ninja.")) == 1


@pytest.mark.parametrize("text,expected", [
    ("a rock star", "rock star"), ("our guru", "guru"), ("a recent graduate", "recent graduate"),
    ("a digital native", "digital native"), ("the manpower plan", "manpower"), ("she will lead", "she will"),
])
def test_other_rules(text, expected):
    assert phrases(text) == [expected]


def test_generated_job_text_is_clean_so_only_voice_note_flags_remain():
    for note in NOTES.values():
        draft = generate_job(note)
        flags = check_requisition(note, draft.job.as_text())
        assert all(f.where == "voice note" for f in flags)


def test_flags_are_stored_and_shown_on_the_requisition_page(hm, db):
    make_req(hm)
    assert [f["phrase"].lower() for f in db.get(Requisition, 1).wording_flags] == ["young and energetic", "native english speaker"]
    hm.post("/requisitions/1/generate")
    html = hm.get("/requisitions/1").text
    assert "young and energetic" in html and "native English speaker" in html and "fluent written and spoken English" in html
    assert "2 flags" in html


# ---- Prompt 9: edit, approve, publish -----------------------------------------------------------------
def generated(hm):
    make_req(hm)
    hm.post("/requisitions/1/generate")


def rubric_form(req, **changes):
    data = {}
    for n, i in enumerate(req.rubric["items"]):
        data[f"weight_{n}"] = str(i["weight"])
        if i["must_have"]:
            data[f"must_{n}"] = "1"
    data.update({k: str(v) for k, v in changes.items()})
    data["min_years"] = str(req.rubric["min_years"])
    return data


def test_edit_that_breaks_the_100_total_is_rejected_with_a_clear_message(hm, db):
    generated(hm)
    form = rubric_form(db.get(Requisition, 1), weight_0=30)
    hm.post("/requisitions/1/rubric", data=form)
    assert "must add to 100" in hm.get("/requisitions/1").text
    assert db.get(Requisition, 1).rubric["items"][0]["weight"] == 19  # unchanged


def test_valid_edit_is_saved_and_needs_new_approval(hm, db):
    generated(hm)
    hm.post("/requisitions/1/approve", data={"comment": "ok"})
    assert db.get(Requisition, 1).status == "APPROVED"
    form = rubric_form(db.get(Requisition, 1), weight_0=20, weight_5=6)  # 19->20 and 7->6: still 100
    hm.post("/requisitions/1/rubric", data=form)
    db.expire_all()
    req = db.get(Requisition, 1)
    assert req.status == "GENERATED" and req.rubric["items"][0]["weight"] == 20
    assert "rubric edited" in [e.action for e in db.query(DecisionLog)]


def test_untick_must_have_and_remove_a_skill(hm, db):
    generated(hm)
    req = db.get(Requisition, 1)
    form = rubric_form(req)
    del form["must_2"]
    form["remove_7"] = "1"  # removes 6 points -> total 94, so give them to skill 6
    form["weight_6"] = str(req.rubric["items"][6]["weight"] + 6)
    hm.post("/requisitions/1/rubric", data=form)
    db.expire_all()
    items = db.get(Requisition, 1).rubric["items"]
    assert len(items) == 7 and items[2]["must_have"] is False and sum(i["weight"] for i in items) == 100


def test_removing_too_many_skills_is_refused(hm, db):
    generated(hm)
    form = rubric_form(db.get(Requisition, 1))
    for n in range(4):
        form[f"remove_{n}"] = "1"
    hm.post("/requisitions/1/rubric", data=form)
    assert len(db.get(Requisition, 1).rubric["items"]) == 8


def test_publishing_before_approval_is_refused_even_when_posted_directly(hm, db):
    generated(hm)
    hm.post("/requisitions/1/publish")
    assert db.get(Requisition, 1).status == "GENERATED"
    assert "can only be published after the rubric is approved" in hm.get("/requisitions/1").text


def test_approval_is_logged_with_email_comment_and_rubric_then_publish(hm, db):
    generated(hm)
    hm.post("/requisitions/1/approve", data={"comment": "Matches my note"})
    hm.post("/requisitions/1/publish")
    assert db.get(Requisition, 1).status == "PUBLISHED"
    e = db.query(DecisionLog).filter_by(action="rubric approved").one()
    assert e.actor == "hm@example.com" and e.reason == "Matches my note"
    assert e.evidence["rubric"]["items"][0]["skill"] == "Linux troubleshooting"
    assert [x.action for x in db.query(DecisionLog).order_by(DecisionLog.id)] == [
        "requisition created", "transcribed", "draft generated", "rubric approved", "job published"]


def test_cannot_approve_twice_or_before_generation(hm, db):
    make_req(hm)
    hm.post("/requisitions/1/approve")
    assert db.get(Requisition, 1).status == "TRANSCRIBED"
    hm.post("/requisitions/1/generate")
    hm.post("/requisitions/1/approve")
    hm.post("/requisitions/1/approve")
    assert db.query(DecisionLog).filter_by(action="rubric approved").count() == 1


def test_approval_refused_while_job_text_contains_a_flagged_phrase(hm, db):
    generated(hm)
    hm.post("/requisitions/1/job", data={"title": "Cloud Support Engineer", "summary": "We want a young and energetic person.",
                                         "responsibilities": "Fix things", "requirements": "Linux", "nice_to_have": ""})
    hm.post("/requisitions/1/approve")
    assert db.get(Requisition, 1).status == "GENERATED"
    assert "biased wording" in hm.get("/requisitions/1").text
    hm.post("/requisitions/1/job", data={"title": "Cloud Support Engineer", "summary": "We want a motivated person to join the team.",
                                         "responsibilities": "Fix things", "requirements": "Linux", "nice_to_have": ""})
    hm.post("/requisitions/1/approve")
    assert db.get(Requisition, 1).status == "APPROVED"


def test_recruiter_cannot_approve_publish_or_edit(hm, db):
    generated(hm)
    with TestClient(app, follow_redirects=False) as rc:
        rc.post("/login", data={"email": "recruiter@example.com", "password": DEMO_PASSWORD})
        for path in ("approve", "publish", "rubric", "job", "generate"):
            assert rc.post(f"/requisitions/1/{path}").status_code == 403
        assert "Approve rubric" not in rc.get("/requisitions/1").text
