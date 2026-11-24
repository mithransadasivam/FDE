"""Day 10: the case workflow's steps (done, not a ticket).

Each function here is a DBOS step: it may touch the world (the bank, CaseFlow Classic, the model), and DBOS saves its output
when it finishes. A step that finished is never run again, even after a crash; a step that was cut off is run again from its
start. That is why ENG-1003 makes every write in a step safe to make twice.

Every step acts as the person who started the case, through the case grant (grants.py), and notes what it did in the case's
event log, which the Workflows screen draws as a timeline.
"""

import csv
import json
import os
import re
import threading
import time

from dbos import DBOS

from app import store
from app.agent import actions, loop, runs
from app.agent import screen as scr
from app.agent.models import Approval
from app.config import CHASE_POLICY_FILE_10, LEGACY_URL, PLAYBOOK_FILE_9, WRITES_FILE_10
from app.integration import notify
from app.integration import tools as bank
from app.integration.downstream import downstream_token
from app.workflow import engine, grants, writes


# A waiting case costs nothing, so the worker runs many at once; a browser costs memory, so at most a few at a time
BROWSERS = threading.BoundedSemaphore(int(os.getenv("FDE_BROWSERS", "3")))


# ---------------------------------------------------------------- the case's event log (what the timeline shows)
def note(key: str, kind: str, text: str, **extra) -> None:
    """Append one event to the case's log. Steps note when they start, so a step that runs twice shows twice.
    One JSON line per event, appended: the worker and the console's API can both write without losing a line."""
    p = store.path(f"workflow/events/{key}.jsonl")
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"at": time.time(), "kind": kind, "text": text, "pid": os.getpid(), **extra})
    with open(p, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def events(key: str) -> list[dict]:
    p = store.path(f"workflow/events/{key}.jsonl")
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


def load_policy() -> dict:
    return json.loads(CHASE_POLICY_FILE_10.read_text(encoding="utf-8"))


def write_rules() -> list[dict]:
    with open(WRITES_FILE_10, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@DBOS.step(name="policy")
def policy() -> dict:
    """The chase policy, read once per workflow: if Grace changes the file, a case already waiting keeps the rule it started with."""
    return load_policy()


# ---------------------------------------------------------------- the agent proposes (ENG-1001)
def _run_agent(key: str, ticket_id: str, prompt: str, round_no: int, approver) -> tuple:
    ident = grants.identity(key)
    run = runs.new_run(ticket_id, ident.sub, prompt)
    run.id = f"{key}-r{round_no}-{run.id[-4:]}"
    run.workflow_id = key
    runs.save_run(run)
    ctx = actions.RunContext(identity=ident, legacy_url=LEGACY_URL, shots_dir=store.path(f"agent/runs/{run.id}"), run=run)
    out = loop.run_agent(ctx, runs.llm_client(), runs.prompt_text(prompt), PLAYBOOK_FILE_9.read_text(encoding="utf-8"),
                         runs.limits(), runs.rules(), approver, runs.save_run)
    return out, ctx


@DBOS.step(name="propose")
def propose(key: str, ticket_id: str, prompt: str, round_no: int) -> dict:
    """The Day 9 agent works the exception up to CaseFlow's confirm screen, then stops: the approval it would ask for is saved
    as pending, for the workflow to wait on. Returns what it proposes, or how its run ended if it never got that far."""
    note(key, "propose", f"Round {round_no}: the agent works {ticket_id}")
    pol = load_policy()
    asked: list[Approval] = []

    def deferred(ap: Approval) -> Approval:
        ap = ap.model_copy(update={"workflow_id": key, "expires_at": time.time() + engine.days(pol["approval_expires_after_days"])})
        runs._save_approval(ap)
        asked.append(ap)
        return ap

    with BROWSERS:
        run, ctx = _run_agent(key, ticket_id, prompt, round_no, deferred)
    out = {"status": run.status, "run_id": run.id, "outcome": run.outcome, "reason_code": run.reason_code,
           "note": ctx.chosen.get("Note", ""), "reason_label": ctx.chosen.get("Reason code", ""),
           "stop_reason": run.stop_reason, "summary": run.summary, "tokens_in": run.tokens_in, "tokens_out": run.tokens_out,
           "approval": asked[-1].model_dump() if asked and run.status == "waiting_approval" else None}
    note(key, "proposed" if out["approval"] else "agent_ended",
         f"Proposed {run.outcome} ({run.reason_code}): waiting for {run.person}" if out["approval"]
         else f"The agent ended its run: {run.status}. {run.stop_reason or run.summary}".strip(), run_id=run.id)
    return out


@DBOS.step(name="expire")
def expire(approval_id: str) -> None:
    """Nobody decided in time: the approval is marked expired, so the card leaves the person's queue."""
    a = next((x for x in runs.approvals() if x["id"] == approval_id), None)
    if a and a["status"] == "pending":
        a.update(status="expired", decided_by="nobody", note="Not decided in time: the case workflow stopped waiting", decided_at=time.time())
        runs._save_approval(Approval(**a))
        note(a["workflow_id"], "expired", f"Approval {approval_id} expired: nobody decided in time")


# ---------------------------------------------------------------- the workflow writes exactly what was approved (ENG-1001, ENG-1003)
def _wait_for(screen: scr.LegacyScreen, title: str, seconds: float = 15) -> list[dict]:
    """The screen whose title starts with `title`: a click returns before the next page has always arrived."""
    end = time.time() + seconds
    while True:
        now = screen.title()
        if now.startswith(title):
            return screen.read()
        if time.time() > end:
            raise scr.ScreenError(f'Expected the screen "{title}…", but CaseFlow shows "{now}"')
        time.sleep(0.2)


def _goto_case(screen: scr.LegacyScreen, els: list[dict], case_id: str) -> list[dict]:
    els = screen.act(scr.find_element(els, "link", "Find a case"), "click")
    els = _wait_for(screen, "Find a case")
    els = screen.act(scr.find_element(els, "textbox", "Case reference"), "type", case_id)
    screen.act(scr.find_element(els, "button", "Search"), "click")
    return _wait_for(screen, f"Case {case_id}")


@DBOS.step(name="apply", retries_allowed=True, max_attempts=3)  # safe to try again: it reads the history before it writes
def apply(key: str, ticket_id: str, proposal: dict, round_no: int) -> dict:
    """Record the approved outcome in CaseFlow Classic, exactly as approved, then comment on the exception.

    No model here: plain code works the screens (find_element, ENG-901) and reads them back (check_saved). The confirm screen
    must show the outcome and reason code the person approved. The note ends with this round's marker (ENG-1003), and the
    case history is read first: if the marker is already there, an earlier attempt recorded it before the worker crashed."""
    note(key, "apply", f"Round {round_no}: recording {proposal['outcome']} in CaseFlow Classic")
    ident = grants.identity(key)
    ex = bank.get_exception(ident, ticket_id)
    marker = writes.outcome_marker(key, round_no)
    screen = scr.LegacyScreen(LEGACY_URL)
    BROWSERS.acquire()
    try:
        els = screen.start(downstream_token(ident, "caseflow", bank.bank_http()))
        els = _goto_case(screen, els, ex["case_id"])
        history = [e["name"] for e in els if e["role"] == "row"]
        if writes.already_recorded(history, marker):
            line = next(h for h in history if marker in h)
            ref = (re.search(r"OUT-\d+", line) or [""])[0]
            note(key, "already", f"Round {round_no}: CaseFlow already has this outcome ({ref}): nothing written again")
            result = {"reference": ref, "already": True}
        else:
            screen.act(scr.find_element(els, "button", "Record outcome"), "click")
            els = _wait_for(screen, "Record outcome")
            els = screen.act(scr.find_element(els, "combobox", "Outcome"), "choose", proposal["outcome"])
            els = screen.act(scr.find_element(els, "combobox", "Reason code"), "choose", proposal["reason_label"])
            text = (proposal["note"][: 238 - len(marker)] + " " + marker).strip()
            els = screen.act(scr.find_element(els, "textbox", "Note"), "type", text)
            screen.act(scr.find_element(els, "button", "Save"), "click")
            els = _wait_for(screen, "Confirm")
            shows = {r[0]: r[1] for r in proposal["approval"]["shows"] if len(r) == 2}
            now = {r["name"].split(" | ", 1)[0]: r["name"].split(" | ", 1)[1] for r in els if r["role"] == "row" and " | " in r["name"]}
            for field in ("Outcome", "Reason code"):
                if now.get(field) != shows.get(field):
                    raise scr.ScreenError(f"The confirm screen shows {field} {now.get(field)!r}, but {proposal['approval']['person']} "
                                          f"approved {shows.get(field)!r}: nothing written")
            screen.act(scr.find_element(els, "button", "Confirm"), "click")
            els = _wait_for(screen, "Outcome recorded")
            ref = scr.check_saved(els, proposal["outcome"])
            engine.crash_point("after_confirm", ticket_id)
            result = {"reference": ref, "already": False}
            note(key, "recorded", f"Round {round_no}: CaseFlow recorded {proposal['outcome']} · {ref}")
    finally:
        screen.close()
        BROWSERS.release()
    token = grants.token_for(key, "kyc-exceptions")
    writes.post(token, f"/kyc/tickets/{ticket_id}/comments",
                {"text": f"Outcome recorded in CaseFlow Classic: {proposal['outcome']} ({proposal['reason_code']}). "
                         f"Reference {result['reference']}. Approved by {proposal['approval']['person']}; recorded by the case workflow."},
                writes.idempotency_key(key, DBOS.step_id) + ":comment")
    return result


# ---------------------------------------------------------------- the chase (ENG-1002)
def _template(kind: str, case_id: str, pol: dict) -> str:
    return pol["templates"][kind].replace("{case}", case_id)


@DBOS.step(name="send_message")
def send_message(key: str, ticket_id: str, kind: str) -> dict:
    """Send the applicant a request for documents, or a reminder, through the bank's contact gateway (ENG-1003's key).
    Returns the message and the documents on file when it was sent."""
    note(key, f"send_{kind}", f"Sending the applicant a {kind}")
    ident = grants.identity(key)
    ex = bank.get_exception(ident, ticket_id)
    known = [d["doc_id"] for d in bank.list_documents(ident, ex["customer_id"]).get("documents", [])]
    msg = writes.post(grants.token_for(key, "contact"), "/contact/messages",
                      {"ticket_id": ticket_id, "kind": kind, "text": _template(kind, ex["case_id"], load_policy())},
                      writes.idempotency_key(key, DBOS.step_id))
    engine.crash_point(f"after_send_{kind}", ticket_id)
    note(key, "sent" if not msg.get("replayed") else "replayed",
         f"{msg['id']}: {kind} sent" if not msg.get("replayed") else f"{msg['id']}: the gateway already had this {kind}: nothing sent again")
    return {"message_id": msg["id"], "replayed": bool(msg.get("replayed")), "known": known}


@DBOS.step(name="new_document")
def new_document(key: str, ticket_id: str, known: list[str]) -> dict | None:
    """Ask the document store whether anything arrived that was not on file before (the starter's polling uses this)."""
    ident = grants.identity(key)
    ex = bank.get_exception(ident, ticket_id)
    for d in bank.list_documents(ident, ex["customer_id"]).get("documents", []):
        if d["doc_id"] not in known:
            return {"ticket_id": ticket_id, "doc_id": d["doc_id"], "doc_type": d["doc_type"]}
    return None


@DBOS.step(name="received")
def received(key: str, doc: dict) -> None:
    """Note on the timeline that the applicant replied (a step, so it is noted once, even if the workflow runs again)."""
    note(key, "documents", f"The applicant sent a {doc['doc_type'].replace('_', ' ')} ({doc['doc_id']})")


@DBOS.step(name="escalate")
def escalate(key: str, ticket_id: str) -> dict:
    """No reply after the last reminder: a comment on the exception for the team lead, then a message in the team's channel."""
    note(key, "escalate", "No reply from the applicant: escalating to the team lead")
    ident = grants.identity(key)
    ex = bank.get_exception(ident, ticket_id)
    pol = load_policy()
    lead = pol["escalate_to"].get(ex["team_id"][0], "the team lead")
    days = pol["escalate_after_days"]
    # the same key on every attempt of this step: after a crash the bank replays the first comment and adds nothing (ENG-1003)
    writes.post(grants.token_for(key, "kyc-exceptions"), f"/kyc/tickets/{ticket_id}/comments",
                {"text": f"Escalated to {lead}: no reply from the applicant {days} days after our request. Recorded by the case workflow."},
                writes.idempotency_key(key, DBOS.step_id))
    engine.crash_point("after_escalate", ticket_id)
    team = notify.TEAM_NAMES.get(ex["team_id"], ex["team_id"])
    msg = {"text": f"Escalated KYC exception {ticket_id} ({team}): no reply from the applicant in {days} days. For {lead}.",
           "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": f"*Escalated: {ticket_id}*\nNo reply from the applicant in {days} days"}},
                      {"type": "context", "elements": [{"type": "mrkdwn", "text": f"{team} · for {lead} · from the case workflow · no customer name in Slack"}]}]}
    bank.bank_http().post(f"{notify.BANK_URL}/slack/hooks/{notify.CHANNEL_FOR_REGION[ex['team_id'][0]]}", json=msg)
    note(key, "escalated", f"Escalated to {lead}")
    return {"lead": lead}


# ---------------------------------------------------------------- the end of a case
@DBOS.step(name="close")
def close(key: str, ticket_id: str, end: str, detail: dict) -> dict:
    """The case is over: the case grant is revoked, and the end is noted."""
    grants.close_grant(key)
    note(key, "end", f"Case ended: {end}", end=end)
    return {"ticket_id": ticket_id, "end": end, **{k: v for k, v in detail.items() if k in ("outcome", "reason_code", "reference", "note")}}


# ---------------------------------------------------------------- before ENG-1001: one step does everything (kept for comparison)
@DBOS.step(name="agent_round")
def agent_round(key: str, ticket_id: str, prompt: str, round_no: int) -> dict:
    """The Day 9 way, inside one step: the agent works the case, waits in memory for the person's approval, then presses
    Confirm itself. If the worker crashes while it waits, the whole step runs again: the agent starts over, and the person is
    asked again."""
    note(key, "propose", f"Round {round_no}: the agent works {ticket_id} (one step: think, wait, write)")
    pol = load_policy()

    def wait_here(ap: Approval) -> Approval:
        ap = ap.model_copy(update={"workflow_id": key, "expires_at": time.time() + engine.days(pol["approval_expires_after_days"])})
        runs._save_approval(ap)
        note(key, "proposed", f"Waiting for {ap.person}, in memory, inside the step")
        while time.time() < ap.expires_at:
            a = next((x for x in runs.approvals() if x["id"] == ap.id), None)
            if a and a["status"] != "pending":
                return Approval(**a)
            time.sleep(0.3)
        a = next(x for x in runs.approvals() if x["id"] == ap.id)
        a.update(status="expired", decided_by="nobody", note="Not decided in time", decided_at=time.time())
        runs._save_approval(Approval(**a))
        return Approval(**a)

    run, ctx = _run_agent(key, ticket_id, prompt, round_no, wait_here)
    end = {"recorded": "recorded", "rejected": "rejected"}.get(run.status, run.status)
    if run.status == "stopped" and "Expired" in run.stop_reason:
        end = "expired"
    if end == "recorded":
        note(key, "recorded", f"Round {round_no}: CaseFlow recorded {run.outcome} · {run.reference}")
    return {"end": end, "outcome": run.outcome, "reason_code": run.reason_code, "reference": run.reference, "run_id": run.id,
            "note": ctx.chosen.get("Note", "")}
