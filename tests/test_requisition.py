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
