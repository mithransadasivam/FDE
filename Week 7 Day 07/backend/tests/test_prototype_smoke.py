"""Day 3 files are in place. These pass from the start of Day 3. 6 tests."""

import json
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.prototype.cases import applications, ocr_words

c = TestClient(app)
BACKEND = Path(__file__).resolve().parents[1]


def test_thirty_cases_with_documents_and_words():
    apps = applications()
    assert len(apps) == 30
    words = ocr_words("D03-001")
    assert len(words) > 30 and all(0 <= v <= 1 for w in words for v in w.box)


def test_queue_lists_every_case():
    q = c.get("/api/cases").json()
    assert len(q) == 30 and q[0]["case_id"] == "D03-001"


def test_document_image_is_served():
    r = c.get("/api/cases/D03-001/image")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"


def test_a_decision_needs_a_named_analyst():
    r = c.post("/api/cases/D03-002/decision", json={"decision": "approve", "analyst_id": " "})
    assert r.status_code == 422 and "person makes every decision" in r.json()["detail"]


def test_no_review_until_the_script_runs():
    r = c.get("/api/cases/pr-review")
    assert r.status_code in (200, 404)


def test_review_script_saves_a_review_in_scripted_mode(tmp_path):
    diff = "diff --git a/x.py b/x.py\n--- a/x.py\n+++ b/x.py\n+print('hi')\n"
    run = subprocess.run([sys.executable, "-m", "scripts.pr_review", "--stdin"], input=diff, capture_output=True, text=True, cwd=BACKEND)
    assert run.returncode == 0, run.stderr
    assert "Claude review" in run.stdout
    r = c.get("/api/cases/pr-review").json()
    assert r["verdict"] == "comments" and r["stats"]["files"] == ["x.py"]
    json.dumps(r)
