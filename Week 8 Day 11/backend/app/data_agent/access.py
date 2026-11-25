"""Who may see what: semantic/access.yml, read for the validator and row security (done, not a ticket)."""

import yaml

from app.config import ACCESS_FILE

_TEAMS = {"N1": ("North 1", "North"), "N2": ("North 2", "North"), "M1": ("Midlands 1", "Midlands"),
          "M2": ("Midlands 2", "Midlands"), "S1": ("South 1", "South"), "S2": ("South 2", "South")}  # caseflow.teams


def policy() -> dict:
    return yaml.safe_load(ACCESS_FILE.read_text(encoding="utf-8"))


def users() -> list[dict]:
    p = policy()
    return [{**u, "sees": p["roles"][u["role"]]["sees"], "scope": describe(u)} for u in p["users"]]


def user(user_id: str) -> dict:
    for u in policy()["users"]:
        if u["id"] == user_id:
            return u
    raise KeyError(f"No user {user_id} in semantic/access.yml")


def teams_for(u: dict) -> list[str] | None:
    """The team ids whose cases this user may see; None means every team."""
    sees = policy()["roles"][u["role"]]["sees"]
    if sees == "all":
        return None
    if sees == "team":
        return [u["team"]]
    if sees == "region":
        return [t for t, (_, region) in _TEAMS.items() if region == u["region"]]
    raise ValueError(f"Unknown scope {sees!r} for role {u['role']}")


def masked_for(u: dict) -> list[str]:
    return list(policy()["roles"][u["role"]].get("masked_columns", []))


def describe(u: dict) -> str:
    """What row security lets this user see, in words, for the screens."""
    teams = teams_for(u)
    hidden = masked_for(u)
    if teams is None:
        where = "All teams' cases"
    else:
        names = [_TEAMS[t][0] for t in teams]
        where = f"Only {names[0]}'s cases" if len(names) == 1 else "Only " + " and ".join(names) + f" ({u.get('region')} region)"
    if hidden:
        where += "; customer names hidden"
    return where
