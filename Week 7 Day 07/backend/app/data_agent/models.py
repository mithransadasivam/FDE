"""Shapes for the Day 7 data agent. The same shapes are in the Day 7 section of frontend/src/api.ts."""

from typing import Literal

from pydantic import BaseModel


class Check(BaseModel):
    """What the validator decided about one query (ticket ENG-701)."""
    ok: bool
    reasons: list[str] = []  # why it was refused, in order; empty when ok
    notes: list[str] = []    # what the validator changed, for example "Added LIMIT 1000"
    sql: str = ""            # the query that may run, with its limit; "" when refused


class SQLReply(BaseModel):
    """What the model writes for one question."""
    sql: str = ""
    explanation: str = ""          # one or two sentences: what the query counts
    assumptions: list[str] = []    # every choice the question left open, such as which date or which statuses
    cannot_answer: str = ""        # set instead of sql when the warehouse cannot answer the question


class Attempt(BaseModel):
    """One query the model wrote, and what happened to it."""
    sql: str
    check: Check
    secured_sql: str = ""   # after row security (ENG-702): the query that ran
    error: str = ""         # the warehouse's error, or the cost check's refusal


Status = Literal["answered", "refused", "error", "cannot_answer"]


class Answer(BaseModel):
    question: str
    question_id: str = ""
    user: str
    layer: str
    status: Status
    attempts: list[Attempt] = []
    columns: list[str] = []
    rows: list[list] = []
    capped: bool = False          # the answer reached the row limit
    explanation: str = ""
    assumptions: list[str] = []
    cannot_answer: str = ""
    scope: str = ""               # what row security let this user see
    tokens_in: int = 0
    tokens_out: int = 0
    ms: int = 0
