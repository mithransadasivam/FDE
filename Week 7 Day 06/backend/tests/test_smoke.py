"""The parts that work from the start: these pass before you change anything."""

import json

from fastapi.testclient import TestClient

from app.discovery.questions import draft_questions
from app.discovery.usecases import load_candidates, score_use_case
from app.main import app
from tests.fakes import FakeClient

api = TestClient(app)


def test_health():
    assert api.get("/api/health").json()["status"] == "ok"


def test_brief_has_key_facts():
    brief = api.get("/api/brief").json()
    labels = [f["label"] for f in brief["facts"]]
    assert "Client" in labels and "Sponsor" in labels
    assert "Kestrelmoor Bank" in brief["markdown"]


def test_question_plan_is_numbered_and_saved():
    qs = api.post("/api/questions/draft").json()
    assert len(qs) >= 10 and qs[0]["id"] == "Q01"
    assert {q["area"] for q in qs} == {"goals", "process", "data", "risk", "success"}
    api.put("/api/questions/Q04", json={"starred": True})
    assert [q["id"] for q in api.get("/api/questions").json() if q["starred"]] == ["Q04"]


def test_question_plan_retries_once_on_bad_json():
    good = json.dumps({"questions": [{"area": "process", "text": f"Question number {i} about the process?", "why": "Because it matters"} for i in range(10)]})
    client = FakeClient("Sure! Here are some questions...", good)
    qs = draft_questions("brief", client)
    assert len(qs) == 10 and len(client.requests) == 2


def test_use_case_scores_and_exclusion():
    ucs = {u.id: u for u in load_candidates()}
    assert score_use_case(ucs["UC5"]) == 0
    assert score_use_case(ucs["UC1"]) > score_use_case(ucs["UC2"])
    r = api.put("/api/usecases/UC5", json={"first_choice": True})
    assert r.status_code == 409
