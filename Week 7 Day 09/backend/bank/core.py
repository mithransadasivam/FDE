"""The bank's systems on your laptop (Day 8): shared settings, the signing key, the people, and saved state.

This package stands in for the client's estate. It is done, and you do not change it: on a real engagement these systems
belong to the bank. Run it with:  python -m bank.server --port 8100
"""

import json
import os
import threading
import time
import uuid
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

REPO = Path(__file__).resolve().parents[2]
DATA = REPO / "data"
BANK_URL = os.getenv("FDE_BANK_URL", "http://localhost:8100").rstrip("/")
ISSUER = BANK_URL + "/"  # the issuer identifier, exactly as the MCP server's metadata names it
MCP_RESOURCE = os.getenv("FDE_MCP_URL", "http://localhost:8200").rstrip("/") + "/mcp"
STATE = Path(os.getenv("FDE_BANK_STATE", REPO / "engagement" / "bank")).resolve()
PASSWORD = "kyc-demo"  # the course accounts' password (fictional bank, course only)

# Resources (RFC 8707): what a token may be used for
RESOURCES = {"crm": "crm", "kyc-exceptions": "kyc-exceptions", "documents": "documents", "caseflow": "caseflow"}  # caseflow: Day 9

PEOPLE = {
    "tom.reyes": {"name": "Tom Reyes", "role": "analyst", "team": "N1", "region": "North", "scopes": ["kyc.read", "kyc.write"]},
    "grace.mensah": {"name": "Grace Mensah", "role": "team_lead", "team": None, "region": "North", "scopes": ["kyc.read", "kyc.write", "kyc.assign"]},
    "helen.achebe": {"name": "Helen Achebe", "role": "mlro", "team": None, "region": None, "scopes": ["kyc.read", "kyc.write"]},
}
TEAMS = {"N1": "North", "N2": "North", "M1": "Midlands", "M2": "Midlands", "S1": "South", "S2": "South"}

# Registered clients. Public clients (Claude Code, the MCP SDK) register themselves at /register.
CLIENTS = {
    "fde-console": {"secret": os.getenv("FDE_CONSOLE_CLIENT_SECRET", "console-secret-dev"), "name": "FDE Engagement Console",
                    "grants": ["authorization_code", "refresh_token"], "redirect": "loopback"},
    "fde-mcp": {"secret": os.getenv("FDE_MCP_CLIENT_SECRET", "mcp-secret-dev"), "name": "FDE MCP server",
                "grants": ["urn:ietf:params:oauth:grant-type:token-exchange"]},
    "svc-fde-console": {"secret": os.getenv("FDE_SERVICE_SECRET", "service-secret-dev"), "name": "Console service account",
                        "grants": ["client_credentials"], "role": "service", "scopes": ["kyc.read", "kyc.write"]},
}

_lock = threading.RLock()


def _path(name: str) -> Path:
    STATE.mkdir(parents=True, exist_ok=True)
    return STATE / name


def load(name: str, default):
    p = _path(name)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def save(name: str, data) -> None:
    with _lock:
        _path(name).write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")


# ---------------------------------------------------------------- the signing key
_KEY = None


def private_key():
    global _KEY
    with _lock:
        if _KEY is None:
            p = _path("signing_key.pem")
            if p.exists():
                _KEY = serialization.load_pem_private_key(p.read_bytes(), password=None)
            else:
                _KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
                p.write_bytes(_KEY.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        return _KEY


KID = "kestrel-2026-11"


def jwks() -> dict:
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private_key().public_key()))
    return {"keys": [{**jwk, "kid": KID, "use": "sig", "alg": "RS256"}]}


def sign(claims: dict, key=None, kid: str = KID, alg: str = "RS256") -> str:
    return jwt.encode(claims, key if key is not None else private_key(), algorithm=alg, headers={"kid": kid})


def issue(sub: str, audience: str, scopes: list[str], client_id: str, lifetime: int = 900, act: dict | None = None,
          now: float | None = None) -> str:
    """An access token for a person (or the service account), for one resource."""
    now = int(now or time.time())
    p = PEOPLE.get(sub, {})
    claims = {"iss": ISSUER, "sub": sub, "aud": audience, "iat": now, "nbf": now, "exp": now + lifetime, "jti": uuid.uuid4().hex,
              "client_id": client_id, "scope": " ".join(scopes), "name": p.get("name", CLIENTS.get(sub, {}).get("name", sub)),
              "role": p.get("role", CLIENTS.get(sub, {}).get("role", "")), "team": p.get("team"), "region": p.get("region")}
    if act:
        claims["act"] = act
    return sign(claims)


def verify(token: str, audience: str) -> dict:
    """How the bank's own systems check a token (jwt raises if it is not valid for them)."""
    return jwt.decode(token, private_key().public_key(), algorithms=["RS256"], audience=audience, issuer=ISSUER, leeway=30)


def teams_for(claims: dict) -> list[str]:
    role = claims.get("role")
    if role in ("mlro", "service"):
        return list(TEAMS)
    if role == "team_lead":
        return [t for t, r in TEAMS.items() if r == claims.get("region")]
    if role == "analyst" and claims.get("team"):
        return [claims["team"]]
    return []


def audit(system: str, claims: dict | None, action: str, target: str, outcome: str, reason: str = "") -> None:
    with _lock:
        log = load("audit.json", [])
        act = (claims or {}).get("act") or {}
        log.append({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "system": system, "actor": (claims or {}).get("sub", "-"),
                    "via": act.get("sub"), "client_id": (claims or {}).get("client_id"), "action": action, "target": target,
                    "outcome": outcome, "reason": reason})
        save("audit.json", log[-500:])
