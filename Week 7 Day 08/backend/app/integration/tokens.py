"""Ticket ENG-801: check every access token the MCP server receives.

The MCP server is a resource server: it never sees a password. Claude Code or the console signs the person in at the
bank's sign-in service and sends the token with every request. This function decides whether that token is genuine,
current, meant for this server, and allows what is asked. Use PyJWT (import jwt).
"""

import time

import jwt

from app.integration.models import Identity, TokenRejected

ALLOWED_ALGORITHMS = ["RS256"]
LEEWAY_S = 60


def verify_access_token(token: str, jwks: dict, issuer: str, audience: str, required_scopes: list[str], now: float | None = None) -> Identity:
    """Return the Identity in `token`, or raise TokenRejected with the first reason that applies, word for word:

      1. Not a JWT at all (it does not split into a header):        "Not a valid token"
      2. The header's alg is not in ALLOWED_ALGORITHMS:              "Algorithm not allowed: none"   (or HS256…)
      3. The header's kid is not a key in `jwks["keys"]`:           "Unknown signing key: attacker-1"
      4. The signature does not match that key:                      "Bad signature"
      5. iss is not `issuer`:                                       "Wrong issuer: https://login.example.net"
      6. aud is not `audience`:                                     "Wrong audience: crm"
      7. exp is past (allow LEEWAY_S seconds):                       "Expired"
      8. A scope in `required_scopes` is missing from the "scope" claim (space-separated):
                                                                     "Missing scope: kyc.read"

    `now` is the time to check against (seconds since 1970); None means time.time().
    The Identity has sub, name, role, team, region, scopes (a list), client_id, expires_at (exp) and token (the token itself).
    """
    now = time.time() if now is None else now
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError:
        raise TokenRejected("Not a valid token")
    alg = header.get("alg")
    if alg not in ALLOWED_ALGORITHMS:
        raise TokenRejected(f"Algorithm not allowed: {alg}")
    kid = header.get("kid")
    jwk = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if jwk is None:
        raise TokenRejected(f"Unknown signing key: {kid}")
    try:
        claims = jwt.decode(token, jwt.algorithms.RSAAlgorithm.from_jwk(jwk), algorithms=ALLOWED_ALGORITHMS,
                            options={"verify_aud": False, "verify_iss": False, "verify_exp": False, "verify_nbf": False, "verify_iat": False})
    except jwt.PyJWTError:
        raise TokenRejected("Bad signature")
    if claims.get("iss") != issuer:
        raise TokenRejected(f"Wrong issuer: {claims.get('iss')}")
    if claims.get("aud") != audience:
        raise TokenRejected(f"Wrong audience: {claims.get('aud')}")
    if now > claims.get("exp", 0) + LEEWAY_S:
        raise TokenRejected("Expired")
    scopes = str(claims.get("scope", "")).split()
    for need in required_scopes:
        if need not in scopes:
            raise TokenRejected(f"Missing scope: {need}")
    return Identity(sub=claims.get("sub", ""), name=claims.get("name", ""), role=claims.get("role", ""), team=claims.get("team"),
                    region=claims.get("region"), scopes=scopes, client_id=claims.get("client_id", ""), expires_at=int(claims.get("exp", 0)),
                    token=token)
