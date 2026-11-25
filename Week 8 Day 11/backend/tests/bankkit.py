"""Day 8 test helpers: the bank's systems in-process, and tokens signed by its key."""

from fastapi.testclient import TestClient

from bank import core
from bank.server import app as bank_app
from app.integration.models import Identity


def bank() -> TestClient:
    return TestClient(bank_app)


def token(user: str = "tom.reyes", **changes) -> str:
    """A token for the MCP server, as the bank would issue it, with any claims changed."""
    p = core.PEOPLE[user]
    claims = {"iss": core.ISSUER, "sub": user, "aud": core.MCP_RESOURCE, "iat": 1_800_000_000, "nbf": 1_800_000_000, "exp": 1_800_000_900,
              "client_id": "test", "scope": " ".join(p["scopes"]), "name": p["name"], "role": p["role"], "team": p["team"], "region": p["region"]}
    claims.update(changes)
    return core.sign(claims)


def live_identity(user: str = "tom.reyes") -> Identity:
    """A real, current token for the MCP server, as the bank issues it."""
    p = core.PEOPLE[user]
    tok = core.issue(user, core.MCP_RESOURCE, p["scopes"], "test")
    return Identity(sub=user, name=p["name"], role=p["role"], team=p["team"], region=p["region"], scopes=p["scopes"], token=tok)
