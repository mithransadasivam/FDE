"""Day 8 smoke tests: they pass before and after the tickets. Run: python -m pytest -q tests/test_integration_smoke.py"""

import base64
import csv
import hashlib
import re
from urllib.parse import parse_qs, urlparse

import jwt
from fastapi.testclient import TestClient

from app.config import PERMISSIONS_FILE_8
from app.integration import notify
from app.integration.mcp_server import mcp
from app.main import app
from bank import core
from tests.bankkit import bank, live_identity


def test_the_bank_publishes_where_to_sign_in_and_its_keys():
    b = bank()
    m = b.get("/.well-known/oauth-authorization-server").json()
    assert m["issuer"] == core.ISSUER and m["code_challenge_methods_supported"] == ["S256"]
    assert "urn:ietf:params:oauth:grant-type:token-exchange" in m["grant_types_supported"]
    assert b.get("/jwks.json").json()["keys"][0]["kid"] == core.KID


def test_a_client_registers_and_signs_tom_in_with_pkce():
    b = bank()
    reg = b.post("/register", json={"client_name": "test", "redirect_uris": ["http://localhost:3999/cb"], "token_endpoint_auth_method": "none"})
    cid = reg.json()["client_id"]
    verifier = "v" * 50
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    q = {"response_type": "code", "client_id": cid, "redirect_uri": "http://localhost:3999/cb", "code_challenge": challenge,
         "code_challenge_method": "S256", "state": "s1", "resource": core.MCP_RESOURCE}
    page = b.get("/authorize", params=q)
    assert "Kestrelmoor Bank" in page.text and "kyc-demo" in page.text
    r = b.post("/authorize", data={**q, "username": "tom.reyes", "password": "kyc-demo"}, follow_redirects=False)
    code = parse_qs(urlparse(r.headers["location"]).query)["code"][0]
    t = b.post("/token", data={"grant_type": "authorization_code", "code": code, "code_verifier": verifier, "client_id": cid,
                               "redirect_uri": "http://localhost:3999/cb"}).json()
    claims = jwt.decode(t["access_token"], options={"verify_signature": False})
    assert claims["sub"] == "tom.reyes" and claims["aud"] == core.MCP_RESOURCE and claims["team"] == "N1"
    assert b.post("/authorize", data={**q, "username": "tom.reyes", "password": "wrong"}).text.count("Wrong user or password") == 1


def test_the_crm_shows_each_person_their_own_remit():
    b = bank()
    n = {u: b.get("/crm/customers", headers={"Authorization": "Bearer " + core.issue(u, "crm", ["kyc.read"], "t")}).json()["total"]
         for u in core.PEOPLE}
    assert n == {"tom.reyes": 12, "grace.mensah": 24, "helen.achebe": 72}
    assert b.get("/crm/customers").status_code == 401


def test_the_bank_exchanges_a_token_for_the_mcp_server():
    b = bank()
    r = b.post("/token", data={"grant_type": "urn:ietf:params:oauth:grant-type:token-exchange", "subject_token": live_identity().token,
                               "subject_token_type": "urn:ietf:params:oauth:token-type:access_token", "audience": "crm",
                               "client_id": "fde-mcp", "client_secret": "mcp-secret-dev"}).json()
    c = jwt.decode(r["access_token"], options={"verify_signature": False})
    assert c["aud"] == "crm" and c["sub"] == "tom.reyes" and c["act"] == {"sub": "fde-mcp"}


def test_the_mcp_server_asks_for_a_token_and_names_the_bank():
    with TestClient(mcp.streamable_http_app()) as c:
        r = c.post("/mcp", json={})
        assert r.status_code == 401 and "resource_metadata=" in r.headers["www-authenticate"]
        prm = c.get("/.well-known/oauth-protected-resource/mcp").json()
        assert prm["resource"] == core.MCP_RESOURCE and prm["authorization_servers"][0] == m_issuer()


def m_issuer():
    return bank().get("/.well-known/oauth-authorization-server").json()["issuer"]


def test_the_slack_message_has_no_customer_name_and_goes_to_the_team():
    t = {"ticket_id": "KX-2001", "case_id": "KC-1", "customer_id": "CU-1", "team_id": "N1", "kind": "escalation", "title": "Escalated", "status": "open"}
    assert notify.channels_for(t) == ["kyc-north", "financial-crime"]
    assert "KX-2001" in notify.message(t)["text"] and "CU-1" not in str(notify.message(t))


def test_the_permission_matrix_lists_seven_tools_for_three_people():
    rows = list(csv.DictReader(open(PERMISSIONS_FILE_8, encoding="utf-8")))
    assert [r["tool"] for r in rows][:3] == ["find_customer", "get_customer", "add_customer_note"] and len(rows) == 7
    assert all(re.match(r"^(allowed( \d+)?|refused)$", r[p]) for r in rows for p in ("tom.reyes", "grace.mensah", "helen.achebe"))


def test_status_lists_the_tickets():
    s = TestClient(app).get("/api/integration/status").json()
    assert set(s["not_built"]) == {"tokens", "webhooks"} and s["claude_command"].endswith("/mcp")
