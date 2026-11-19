"""Ticket ENG-801: check every access token the MCP server receives. Run: python -m pytest -q tests/test_tokens.py"""

import json

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.integration.models import Identity, TokenRejected
from app.integration.tokens import verify_access_token
from bank import core
from tests.bankkit import token

NOW = 1_800_000_100
JWKS = core.jwks()


def check(tok, scopes=("kyc.read",), now=NOW, audience=core.MCP_RESOURCE):
    return verify_access_token(tok, JWKS, core.ISSUER, audience, list(scopes), now=now)


def reason(tok, **kw):
    with pytest.raises(TokenRejected) as e:
        check(tok, **kw)
    return str(e.value)


def test_a_valid_token_gives_the_person():
    i = check(token("grace.mensah"))
    assert isinstance(i, Identity) and i.sub == "grace.mensah" and i.role == "team_lead" and i.region == "North"
    assert i.scopes == ["kyc.read", "kyc.write", "kyc.assign"] and i.expires_at == 1_800_000_900 and i.client_id == "test"
    assert i.token == token("grace.mensah")


def test_expired_with_a_minute_of_leeway():
    assert check(token(), now=1_800_000_900 + 59).sub == "tom.reyes"
    assert reason(token(), now=1_800_000_900 + 61) == "Expired"


def test_a_token_for_another_system_or_issuer():
    assert reason(token(aud="crm")) == "Wrong audience: crm"
    assert reason(token(iss="https://login.example.net")) == "Wrong issuer: https://login.example.net"


def test_a_key_the_bank_never_published():
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert reason(core.sign({"sub": "tom.reyes"}, key=other, kid="attacker-1")) == "Unknown signing key: attacker-1"
    assert reason(core.sign({"sub": "tom.reyes", "iss": core.ISSUER}, key=other)) == "Bad signature"


def test_a_changed_role_breaks_the_signature():
    h, _, s = token().split(".")
    forged = jwt.utils.base64url_encode(json.dumps({"sub": "tom.reyes", "role": "mlro", "aud": core.MCP_RESOURCE}).encode()).decode()
    assert reason(f"{h}.{forged}.{s}") == "Bad signature"


def test_only_rs256_is_accepted():
    body = jwt.utils.base64url_encode(json.dumps({"sub": "tom.reyes"}).encode()).decode()
    none = jwt.utils.base64url_encode(b'{"alg":"none","typ":"JWT"}').decode() + "." + body + "."
    assert reason(none) == "Algorithm not allowed: none"
    assert reason(jwt.encode({"sub": "tom.reyes"}, "secret", algorithm="HS256", headers={"kid": core.KID})) == "Algorithm not allowed: HS256"


def test_scopes_and_garbage():
    assert reason(token(scope="profile")) == "Missing scope: kyc.read"
    assert reason(token(), scopes=("kyc.read", "kyc.assign")) == "Missing scope: kyc.assign"
    assert reason("not-a-token") == "Not a valid token"


def test_the_sign_in_tab_shows_nine_of_nine(monkeypatch):
    from app.integration import service
    from tests.bankkit import bank

    b = bank()
    monkeypatch.setattr(service, "_get", lambda path, **kw: b.get(path, **kw).json())
    s = service.token_probes()
    assert s["summary"] == {"passed": 9, "total": 9}
