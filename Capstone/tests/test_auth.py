import pytest
from fastapi import Depends
from fastapi.testclient import TestClient

from app.auth import HM, hash_password
from app.main import app
from app.models import User
from scripts.create_users import DEMO_PASSWORD, create_users


@app.get("/_hm_only")
def _hm_only(user=Depends(HM)):
    return {"ok": True}


@pytest.fixture
def client(db):
    create_users(db)
    with TestClient(app, follow_redirects=False) as c:
        yield c


def sign_in(client, email="hm@example.com", password=DEMO_PASSWORD):
    return client.post("/login", data={"email": email, "password": password})


def test_both_demo_users_can_sign_in(client):
    for email in ("hm@example.com", "recruiter@example.com"):
        r = sign_in(client, email)
        assert r.status_code == 303 and r.headers["location"] == "/"


def test_wrong_password_is_refused_and_stays_on_login(client):
    r = sign_in(client, password="nope")
    assert r.status_code == 401 and "Wrong email or password" in r.text
    assert client.get("/").status_code == 303  # still signed out


def test_stored_password_is_a_bcrypt_hash_not_the_password(db, client):
    for u in db.query(User).all():
        assert u.password_hash != DEMO_PASSWORD and u.password_hash.startswith("$2")
    assert hash_password("x") != hash_password("x")  # salted


def test_signed_out_staff_page_redirects_to_login(client):
    for path in ("/", "/log", "/_hm_only"):
        r = client.get(path)
        assert r.status_code == 303 and r.headers["location"] == "/login"


def test_recruiter_gets_403_on_hiring_manager_page(client):
    sign_in(client, "recruiter@example.com")
    assert client.get("/_hm_only").status_code == 403
    sign_in(client, "hm@example.com")
    assert client.get("/_hm_only").status_code == 200


def test_create_users_does_nothing_twice(db):
    create_users(db)
    create_users(db)
    assert db.query(User).count() == 2


def test_logout_signs_out(client):
    sign_in(client)
    assert client.get("/").status_code == 200
    client.post("/logout")
    assert client.get("/").status_code == 303
