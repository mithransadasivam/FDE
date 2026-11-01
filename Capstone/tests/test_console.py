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


def test_the_sidebar_is_short_and_every_older_page_is_still_reachable_from_a_tab_bar(client):
    """The sidebar was cut from 20+ items to a handful. Related pages share a tab bar, so nothing was removed: it was grouped."""
    from app.web.common import TAB_SETS

    hm = [label for label, _ in MENUS["hiring_manager"]]
    rc = [label for label, _ in MENUS["recruiter"]]
    assert {"Jobs", "Candidates (blind)", "Screening", "Insights"} <= set(hm) and {"Jobs", "Candidates", "Interviews", "Copilot", "Inbox", "Insights"} <= set(rc)
    assert len(MENUS["recruiter"]) <= 10 and not {"Outbox", "Copilot", "Review queue", "Inbox"} & set(hm)
    reachable = {h for ts in TAB_SETS.values() for _l, h in ts["tabs"]} | {h for _l, h in MENUS["recruiter"]}
    for page in ("/pipeline", "/compare", "/review", "/outbox", "/data-requests", "/trust", "/compliance", "/log", "/analytics"):
        assert page in reachable, page
    sign_in(client, "recruiter@example.com")
    html = client.get("/pipeline").text
    assert 'class="tabs"' in html and 'href="/compare"' in html and 'href="/candidates"' in html
    assert 'class="nav active" href="/candidates"' in html  # the Board tab keeps Candidates highlighted
    assert 'href="/trust"' in client.get("/log").text  # the decision log sits in Insights next to Trust & cost


def test_home_shows_counts_and_log_lists_entries(client, db):
    sign_in(client, "hm@example.com")
    html = client.get("/").text
    for label in ("Requisitions", "Published jobs", "Candidates", "Fields to review"):
        assert label in html
    db.add(DecisionLog(actor="tester", action="something happened", subject="x:1"))
    db.commit()
    assert "something happened" in client.get("/log").text
