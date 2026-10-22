"""Day 14 homework: a fact-checker for the content team.

    writer --> fact_checker --> (writer, while a claim has no support) --> reviewer --> human

The fact-checker reads a draft notice next to the research notes and lists every claim the notes do
not support. The writer gets those claims back to fix, within MAX_REVISIONS. It does not judge style:
that stays the reviewer's job.

app/team.py is not changed. The team is extended through build_team()'s extension points:
extra_nodes, route_fn, state_schema and feedback_fn.
"""

from pydantic import BaseModel, Field

from app.handoffs import HandoffError, Notice, ResearchNotes, ask_for
from app.meter import label
from app.rag import MODEL, llm_client
from app.team import (
    MAX_REVISIONS,
    TeamState,
    build_team,
    handoff,
    route,
    writer_feedback,
)


class FactCheck(BaseModel):
    """Fact-checker -> supervisor (and, through the supervisor, the writer)."""

    claims_checked: int = Field(ge=0, description="How many checkable claims the notice makes")
    unsupported: list[str] = Field(
        default_factory=list,
        description="Each claim the notes do not support: the quoted claim, then what is wrong",
    )


FACT_CHECKER_PROMPT = """You are the fact-checker in an IT communications team. You get research notes
(the only facts we have) and a draft IT notice. Check every claim in the notice against the notes.

1. List every checkable claim in the title, body and actions: times, dates, numbers, causes, what is
   affected, who is affected, what staff must do, and promises about what happens next.
   Set claims_checked to how many you found.
2. A claim is supported when a fact in the notes says it. Rewording is fine.
3. A claim is unsupported when no fact in the notes says it, or when it goes further than the notes
   (a made-up time, a guessed cause, a number of people, an estimated fix time, a promise).
4. For each unsupported claim write one line: the claim in quotes, then what is wrong with it.
   Quote the notice exactly. If every claim is supported, leave unsupported empty.
5. Do not judge style, tone or length: that is the reviewer's job. Only check facts."""


def fact_check(notes: ResearchNotes, notice: Notice, client, model: str = MODEL) -> FactCheck:
    label(client, "fact checker")
    user = (
        "Research notes:\n"
        + notes.model_dump_json(indent=1)
        + "\n\nDraft notice:\n"
        + notice.model_dump_json(indent=1)
    )
    return ask_for(client, model, FACT_CHECKER_PROMPT, user, FactCheck)


# ------------------------------------------------------------------ state
class FactCheckedState(TeamState, total=False):
    # The result of the latest check, with the draft it was made on. The writer node does not know
    # about this key, so it cannot clear it: route() compares the draft instead.
    fact_check: dict | None


def checked_this_draft(state: dict) -> dict | None:
    """The fact check of the current draft, or None if this draft has not been checked yet."""
    fc = state.get("fact_check")
    if fc and fc.get("draft") == state.get("draft"):
        return fc
    return None


# ------------------------------------------------------------------ routing
def route_with_fact_check(state: dict) -> str:
    """The class rule first. Only where it would send a draft to the reviewer do we step in."""
    nxt = route(state)
    if nxt != "reviewer":
        return nxt
    fc = checked_this_draft(state)
    if fc is None:
        return "fact_checker"
    if fc["unsupported"] and (state.get("revisions") or 0) < MAX_REVISIONS:
        return "writer"
    return "reviewer"


def feedback_with_fact_check(state: dict) -> list[str]:
    """What the writer must fix: the class feedback plus every unsupported claim found."""
    feedback = writer_feedback(state)
    fc = checked_this_draft(state)
    if fc:
        feedback += [
            f"Not supported by the research notes, remove or fix: {claim}"
            for claim in fc["unsupported"]
        ]
    return feedback


# ------------------------------------------------------------------ the team
def build_team_with_fact_checker(client=None, model: str = MODEL, **kwargs):
    """build_team() with a fact-checker between the writer and the reviewer."""
    # build_team() makes its own client when none is given; the node needs the same one.
    client = client or llm_client()

    def fact_checker(state):
        try:
            result = fact_check(
                ResearchNotes(**state["research"]), Notice(**state["draft"]), client, model
            )
        except HandoffError as e:
            return {"status": f"stopped: fact-checker handoff failed: {e}"}
        return {
            "fact_check": {**result.model_dump(), "draft": state["draft"]},
            **handoff(
                "fact_checker",
                "supervisor",
                f"{len(result.unsupported)} unsupported of {result.claims_checked} claims",
            ),
        }

    return build_team(
        client,
        model=model,
        route_fn=route_with_fact_check,
        extra_nodes={"fact_checker": fact_checker},
        state_schema=FactCheckedState,
        feedback_fn=feedback_with_fact_check,
        **kwargs,
    )
