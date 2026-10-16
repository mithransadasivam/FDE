"""CaseDesk: the one object the app and the scripts talk to. It owns the team graph and its SQLite checkpoint file, so a
case that is waiting for a person (or for a vendor) is saved on disk and picked up again exactly where it stopped, even
after the program restarts.

    desk.submit("REQ-007")                      a new request becomes a case and runs until a person is needed
    desk.reply("VOB-001", "REQ-001-R1")         the vendor's reply resumes the SAME case from its checkpoint
    desk.act("VOB-002", "approve", "alex@example.com")   a person's decision at the gate
    desk.escalate_stale()                       policy §9: 2 days -> manager's queue, 7 days -> stopped
"""
import os
import sqlite3
from datetime import datetime, timedelta, timezone

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from vendor_desk import audit, casestore, config, rules
from vendor_desk.notes import case_id_for
from vendor_desk.states import State
from vendor_desk.team import LocalWriter, McpWriter, Team, allowed_actions


class CaseDesk:
    def __init__(self, llm, backend, writer=None, parallel: bool = False, checkpoint_path=None,
                 supervisor_mode: str = "rule"):
        self.llm, self.backend = llm, backend
        path = checkpoint_path or (audit.team_dir() / "checkpoints.sqlite")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.saver = SqliteSaver(self.conn)
        self.team = Team(llm, backend, writer or LocalWriter(), self.saver, parallel, supervisor_mode)

    def close(self):
        self.conn.close()

    # ------------------------------------------------------------------ running the graph
    def _cfg(self, case_id: str) -> dict:
        return {"configurable": {"thread_id": case_id}}

    def _run(self, graph_input, case_id: str, on_event=None) -> dict:
        for update in self.team.graph.stream(graph_input, self._cfg(case_id), stream_mode="updates"):
            for node, value in update.items():
                if node == "__interrupt__":
                    if on_event:
                        on_event("gate: waiting for a person (case saved in the checkpoint)")
                elif on_event and isinstance(value, dict):
                    for line in value.get("log", []):
                        if line:
                            on_event(line)
        return casestore.load(case_id)

    def waiting_at_gate(self, case_id: str) -> bool:
        snap = self.team.graph.get_state(self._cfg(case_id))
        return "gate" in (snap.next or ())

    # ------------------------------------------------------------------ the API
    def submit(self, request_id: str, on_event=None) -> dict:
        case_id = case_id_for(request_id)
        return self._run({"case_id": case_id, "mode": "new", "thread": [request_id]}, case_id, on_event)

    def reply(self, case_id: str, reply_request_id: str, on_event=None) -> dict:
        case = casestore.load(case_id)
        if case is None or case["status"] != State.WAITING_FOR_VENDOR.value:
            raise ValueError(f"{case_id} is not waiting for a vendor reply.")
        return self._run({"case_id": case_id, "mode": "reply", "reply_id": reply_request_id}, case_id, on_event)

    def act(self, case_id: str, action: str, person: str, comment: str = "", on_event=None) -> dict:
        """A person's decision. Returns {'ok': bool, 'message': str, 'case': dict}."""
        case = casestore.load(case_id)
        if case is None:
            return {"ok": False, "message": f"There is no case {case_id}.", "case": None}
        allowed = allowed_actions(case)
        if not person.strip():
            return {"ok": False, "message": "A decision needs a named person.", "case": case}
        if action not in allowed:
            audit.append(case_id, person.strip(), "refused", f"{action} is not allowed while the case is {case['status']}")
            return {"ok": False, "case": case, "message": (
                f"'{action}' is not allowed while the case is {case['status']}. Allowed now: "
                f"{', '.join(allowed) or 'nothing (the case is closed)'}.")}
        before = len(case["approvals"])
        if self.waiting_at_gate(case_id):
            case = self._run(Command(resume={"action": action, "person": person.strip(), "comment": comment}),
                             case_id, on_event)
        elif action == "reject":
            audit.append(case_id, person.strip(), "decision", "rejected the vendor", comment)
            casestore.transition(case, State.REJECTED, comment or "rejected by a person", person.strip(), True)
            case["next_step"] = "closed by a person"
            casestore.save(case)
        elif action == "rerun":
            case = self._run({"case_id": case_id, "mode": "rerun", "person": person.strip()}, case_id, on_event)
        else:
            return {"ok": False, "case": case, "message": f"'{action}' is not possible: the case is not waiting for a decision."}
        refused = [e for e in audit.read(case_id) if e["event"] == "refused"][-1:] if action == "approve" and \
            len(case["approvals"]) == before and case["status"] == State.READY_FOR_APPROVAL.value else []
        return {"ok": not refused, "message": refused[0]["detail"] if refused else f"{action} recorded for {case_id}.",
                "case": case}

    # ------------------------------------------------------------------ policy §9: cases that wait too long
    def escalate_stale(self, now: datetime | None = None) -> list[str]:
        """>2 days waiting for approval: manager's queue and a reminder. >7 days: stopped ('approval expired').
        Never approves anything. Returns what it did."""
        now = now or datetime.now(timezone.utc)
        done = []
        for case in casestore.list_cases():
            if case["status"] != State.READY_FOR_APPROVAL.value or not case["ready_since"]:
                continue
            age = now - datetime.fromisoformat(case["ready_since"])
            cid = case["case_id"]
            if age > timedelta(days=rules.STALE_EXPIRE_DAYS):
                reason = f"approval expired (policy §9.2): waiting {age.days} days with no decision"
                case["stop_reason"], case["next_step"] = reason, "stopped: " + reason
                casestore.transition(case, State.STOPPED, reason)
                audit.append(cid, "system", "reminder", "expired: a person must restart this case", reason)
                done.append(f"{cid}: stopped ({reason})")
            elif age > timedelta(days=rules.STALE_MANAGER_DAYS) and not case["manager_queue"]:
                case["manager_queue"] = True
                case["next_step"] = f"manager's queue: waiting {age.days} days for approval ({case['next_step']})"
                casestore.save(case)
                audit.append(cid, "system", "reminder", f"waiting {age.days} days: moved to the manager's queue (policy §9.1)")
                done.append(f"{cid}: moved to the manager's queue")
        return done

    def case(self, case_id: str) -> dict | None:
        return casestore.load(case_id)

    def cases(self) -> list[dict]:
        return casestore.list_cases()


def make_desk(llm_mode: str | None = None, tools: str | None = None, parallel: bool | None = None,
              supervisor: str | None = None) -> CaseDesk:
    """Build a desk from the settings: LLM_MODE (live|offline), TOOLS_BACKEND (local|mcp), TEAM_PARALLEL (on|off)."""
    from vendor_desk.backends import make_backend
    from vendor_desk.llm import make_llm
    backend = make_backend(tools)
    if parallel is None:
        parallel = os.getenv("TEAM_PARALLEL", "off").lower() in ("on", "1", "true")
    writer = McpWriter() if (tools or os.getenv("TOOLS_BACKEND", "local")).lower() == "mcp" else LocalWriter()
    return CaseDesk(make_llm(llm_mode), backend, writer, parallel,
                    supervisor_mode=supervisor or os.getenv("SUPERVISOR", "rule"))
