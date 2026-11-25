"""Ticket ENG-1002: chase the applicant on a clock that survives a crash.

The playbook (data/Day10_Slide10_chase_policy.json): ask the applicant for the documents, send a reminder after 3 days without
a reply, and escalate to the team lead after 7. When the applicant sends a document, the document store calls the console's
webhook, and the console sends the case workflow a message on the topic DOCUMENTS (routes.py).

This function is workflow code, not a step: DBOS runs it again from the top after a crash, and it must make the same calls in
the same order. So it never reads the clock and never sleeps: it waits with DBOS.recv(DOCUMENTS, timeout_seconds), whose
deadline DBOS saves. engine.days(n) turns course days into seconds.
"""

from dbos import DBOS

from app.workflow import engine, steps

DOCUMENTS = "documents"


def chase(key: str, ticket_id: str, policy: dict) -> dict | None:
    """Chase the applicant. Return the document event as soon as one arrives, or None once the case is escalated.

      1. steps.send_message(key, ticket_id, "request")
      2. wait for a message on DOCUMENTS for policy["reminder_after_days"] days: if one comes, return it
      3. steps.send_message(key, ticket_id, "reminder")
      4. wait for the rest of policy["escalate_after_days"] (7 - 3 = 4 more days): if one comes, return it
      5. steps.escalate(key, ticket_id), and return None
    Call steps.received(key, doc) when a document arrives (it notes it on the timeline).
    """
    steps.send_message(key, ticket_id, "request")
    doc = DBOS.recv(DOCUMENTS, timeout_seconds=engine.days(policy["reminder_after_days"]))
    if doc:
        steps.received(key, doc)
        return doc
    steps.send_message(key, ticket_id, "reminder")
    doc = DBOS.recv(DOCUMENTS, timeout_seconds=engine.days(policy["escalate_after_days"] - policy["reminder_after_days"]))
    if doc:
        steps.received(key, doc)
        return doc
    steps.escalate(key, ticket_id)
    return None
