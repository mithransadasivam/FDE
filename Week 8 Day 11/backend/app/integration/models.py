"""Shapes for Day 8. The same shapes are in the Day 8 section of frontend/src/api.ts."""

from pydantic import BaseModel


class Identity(BaseModel):
    """The person behind a request, as a checked token says (ticket ENG-801)."""
    sub: str                 # tom.reyes
    name: str = ""
    role: str = ""           # analyst | team_lead | mlro
    team: str | None = None
    region: str | None = None
    scopes: list[str] = []
    client_id: str = ""      # the app the person signed in to: Claude Code, the console…
    expires_at: int = 0
    token: str = ""          # the token itself, kept only to exchange it (ENG-802); never sent on to another system


class TokenRejected(Exception):
    """The token cannot be used here. str(e) is the reason, word for word as ENG-801 lists it."""


class WebhookRejected(Exception):
    """The delivery is not a genuine, fresh, first delivery. str(e) is the reason (ENG-803)."""


class ToolRefused(Exception):
    """A system of record said no: str(e) is its reason, passed back to the person."""
