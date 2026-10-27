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
        assert f'href="{href}"' in html and label in html
    assert absent not in html


def test_menu_sizes():
    assert len(MENUS["hiring_manager"]) == 4 and len(MENUS["recruiter"]) == 5


def test_home_shows_counts_and_log_lists_entries(client, db):
    sign_in(client, "hm@example.com")
    html = client.get("/").text
    for label in ("Requisitions", "Published jobs", "Candidates", "Fields to review"):
        assert label in html
    db.add(DecisionLog(actor="tester", action="something happened", subject="x:1"))
    db.commit()
    assert "something happened" in client.get("/log").text
