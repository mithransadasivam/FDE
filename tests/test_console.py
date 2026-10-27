from html import escape

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import DecisionLog
from app.web.common import MENUS
from scripts.create_users import DEMO_PASSWORD, create_users


@pytest.fixture
def client(db):
    create_users(db)
    with TestClient(app, follow_redirects=False) as c:
        yield c


def sign_in(client, email):
    client.post("/login", data={"email": email, "password": DEMO_PASSWORD})


def test_health_needs_no_sign_in(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


@pytest.mark.parametrize("email,role,absent", [
    ("hm@example.com", "hiring_manager", "Review queue"),
    ("recruiter@example.com", "recruiter", "Candidates (blind)"),
])
def test_each_role_sees_its_own_menu(client, email, role, absent):
    sign_in(client, email)
    html = client.get("/").text
    for label, href in MENUS[role]:
        assert f'href="{href}"' in html and escape(label) in html
    assert absent not in html


def test_menus_keep_the_day_one_items_and_the_recruiter_has_the_working_tools():
    hm = [label for label, _ in MENUS["hiring_manager"]]
    rc = [label for label, _ in MENUS["recruiter"]]
    assert {"Requisitions", "Candidates (blind)", "Pipeline", "Decision log"} <= set(hm)
    assert {"Requisitions", "Candidates", "Review queue", "Pipeline", "Decision log"} <= set(rc)
    assert {"Outbox", "Copilot", "Compliance"} <= set(rc) and not {"Outbox", "Copilot", "Review queue"} & set(hm)


def test_home_shows_counts_and_log_lists_entries(client, db):
    sign_in(client, "hm@example.com")
    html = client.get("/").text
    for label in ("Requisitions", "Published jobs", "Candidates", "Fields to review"):
        assert label in html
    db.add(DecisionLog(actor="tester", action="something happened", subject="x:1"))
    db.commit()
    assert "something happened" in client.get("/log").text
