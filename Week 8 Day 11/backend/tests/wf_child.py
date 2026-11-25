"""Day 10 test helper: a workflow worker in its own process, with the steps replaced by fakes that record every call.

The tests start it, kill it as a crash would, and start it again, so DBOS recovers the workflow as it does in the real worker.
    python tests/wf_child.py run <workflow> <id> [--crash-after S]      start (or recover) a workflow; die after S seconds
Every fake step appends one JSON line to $WF_CALLS: {"step": …, "t": …}. The result goes to $WF_RESULT.
"""

import json
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dbos import DBOS, SetWorkflowID  # noqa: E402

from app.workflow import case, chase, engine, steps  # noqa: E402

CALLS, RESULT, CTRL = Path(os.environ["WF_CALLS"]), Path(os.environ["WF_RESULT"]), Path(os.environ["WF_CTRL"])


def log(step: str, **kw) -> None:
    with open(CALLS, "a") as f:
        f.write(json.dumps({"step": step, "t": time.time(), **kw}) + "\n")


def ctrl() -> dict:
    try:
        return json.loads(CTRL.read_text())
    except (OSError, ValueError):
        return {}


@DBOS.step(name="propose")
def fake_propose(key, ticket_id, prompt, round_no):
    log("propose", round=round_no)
    if ctrl().get("agent_ends"):
        return {"status": ctrl()["agent_ends"], "approval": None, "outcome": "", "reason_code": "", "run_id": "r1"}
    return {"status": "waiting_approval", "run_id": "r1", "outcome": "Request more information", "reason_code": "R02",
            "reason_label": "R02 Missing proof of address", "note": "Proof of address needed.",
            "approval": {"id": f"A-{round_no}", "person": "tom.reyes", "shows": [["Outcome", "Request more information"]]}}


@DBOS.step(name="apply")
def fake_apply(key, ticket_id, proposal, round_no):
    log("apply", round=round_no)
    return {"reference": "OUT-1", "already": False}


@DBOS.step(name="expire")
def fake_expire(approval_id):
    log("expire", approval=approval_id)


@DBOS.step(name="agent_round")
def fake_agent_round(key, ticket_id, prompt, round_no):
    log("agent_round", round=round_no)  # the agent runs, then waits in memory for the decision
    while not ctrl().get("decision"):
        time.sleep(0.05)
    d = ctrl()["decision"]
    if d == "approved":
        log("apply", round=round_no)
        return {"end": "recorded", "outcome": "Request more information", "reason_code": "R02", "reference": "OUT-1"}
    return {"end": d, "outcome": "Request more information", "reason_code": "R02", "reference": ""}


@DBOS.step(name="send_message")
def fake_send(key, ticket_id, kind):
    log(f"send_{kind}")
    return {"message_id": "MSG-1", "replayed": False, "known": []}


@DBOS.step(name="new_document")
def fake_new_document(key, ticket_id, known):
    log("new_document")
    return ctrl().get("doc")


@DBOS.step(name="escalate")
def fake_escalate(key, ticket_id):
    log("escalate")
    return {"lead": "Grace Mensah (team lead, North)"}


@DBOS.step(name="received")
def fake_received(key, doc):
    log("received", doc=doc.get("doc_id"))


steps.propose, steps.apply, steps.expire, steps.agent_round = fake_propose, fake_apply, fake_expire, fake_agent_round
steps.send_message, steps.new_document, steps.escalate, steps.received = fake_send, fake_new_document, fake_escalate, fake_received
POLICY = {"reminder_after_days": int(os.getenv("WF_REMIND", "3")), "escalate_after_days": int(os.getenv("WF_ESCALATE", "7")),
          "approval_expires_after_days": int(os.getenv("WF_EXPIRE", "3")), "outcomes_that_wait": ["Request more information"]}


@DBOS.workflow(name="t_round")
def t_round(ticket_id: str) -> dict:
    return case.work_round(DBOS.workflow_id, ticket_id, "ops_v3", 1, POLICY)


@DBOS.workflow(name="t_chase")
def t_chase(ticket_id: str):
    return chase.chase(DBOS.workflow_id, ticket_id, POLICY)


if __name__ == "__main__":
    _, mode, wf, wid, *rest = sys.argv
    crash_after = float(rest[rest.index("--crash-after") + 1]) if "--crash-after" in rest else None
    engine.configure(Path(os.environ["FDE_WORKFLOW_DB"]))
    DBOS.launch()  # recovers any workflow left unfinished by a crash
    with open(CALLS.with_name("launches.jsonl"), "a") as f:
        f.write(json.dumps({"t": time.time()}) + "\n")
    if crash_after is not None:  # die `crash_after` seconds after the workflow's first step, as a crash would
        def crash():
            while not CALLS.exists():
                time.sleep(0.01)
            first = json.loads(CALLS.read_text().splitlines()[0])["t"]
            time.sleep(max(0.0, first + crash_after - time.time()))
            os._exit(1)
        threading.Thread(target=crash, daemon=True).start()
    fn = {"t_round": t_round, "t_chase": t_chase}[wf]
    try:
        h = DBOS.retrieve_workflow(wid)
    except Exception:
        h = None
    if h is None:
        with SetWorkflowID(wid):
            h = DBOS.start_workflow(fn, "KX-1001")
    RESULT.write_text(json.dumps({"result": h.get_result()}))
    os._exit(0)
