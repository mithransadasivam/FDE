"""Ticket ENG-1001: work one round of a case as checkpoints: the agent proposes, the person decides, the workflow writes.

On Day 9 the agent waited for Tom's approval inside its own run, in the console's memory. A restart lost the approval, and
running the agent again meant new model calls and a second approval for Tom. In a workflow, each of the three parts is its own
checkpoint, so a crash in the middle loses nothing:

  steps.propose()   a step: the agent works the case up to CaseFlow's confirm screen and saves the approval it needs
  DBOS.recv()       the workflow waits for the person's decision: minutes or days, and through any number of restarts
  steps.apply()     a step: plain code records exactly the approved outcome in CaseFlow, and reads it back

The console sends the decision to the workflow on the approval's own id as the topic (routes.py: decide).

work_case() below is the whole case (done): round 1, then the chase (ENG-1002) if the outcome waits for the applicant, then
round 2 when the documents arrive.
"""

from dbos import DBOS

from app.workflow import engine, steps
from app.workflow.chase import chase


def work_round(key: str, ticket_id: str, prompt: str, round_no: int, policy: dict) -> dict:
    """One round. Returns a dict with "end" and what was proposed:

      1. p = steps.propose(key, ticket_id, prompt, round_no)
         If p["approval"] is None, the agent ended without proposing (stopped, handed back): return {"end": p["status"], **p}
      2. d = DBOS.recv(p["approval"]["id"], timeout_seconds=engine.days(policy["approval_expires_after_days"]))
         No decision in time (None): steps.expire(p["approval"]["id"]) and return {"end": "expired", **p}
      3. If d["status"] is not "approved": return {"end": "rejected", "note": d.get("note", ""), **p}
      4. a = steps.apply(key, ticket_id, p, round_no) and return {"end": "recorded", **p, "reference": a["reference"]}
    """
    p = steps.propose(key, ticket_id, prompt, round_no)
    if p["approval"] is None:
        return {"end": p["status"], **p}
    d = DBOS.recv(p["approval"]["id"], timeout_seconds=engine.days(policy["approval_expires_after_days"]))
    if d is None:
        steps.expire(p["approval"]["id"])
        return {"end": "expired", **p}
    if d["status"] != "approved":
        return {"end": "rejected", "note": d.get("note", ""), **p}
    a = steps.apply(key, ticket_id, p, round_no)
    return {"end": "recorded", **p, "reference": a["reference"]}


@DBOS.workflow(name="work_case")
def work_case(ticket_id: str, prompt: str) -> dict:
    """A KYC exception from start to end, for the person who started it (the case grant says who)."""
    key = DBOS.workflow_id
    policy = steps.policy()
    first = work_round(key, ticket_id, prompt, 1, policy)
    if first["end"] != "recorded" or first["outcome"] not in policy["outcomes_that_wait"]:
        return steps.close(key, ticket_id, first["end"], first)
    doc = chase(key, ticket_id, policy)
    if doc is None:
        return steps.close(key, ticket_id, "escalated", first)
    second = work_round(key, ticket_id, prompt, 2, policy)
    return steps.close(key, ticket_id, "completed" if second["end"] == "recorded" else second["end"], second)
