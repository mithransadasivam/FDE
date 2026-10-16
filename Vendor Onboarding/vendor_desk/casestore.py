"""The case record: the one place the app (Inbox, Case tab) reads a case's current status from.

runs/team/<case_id>/case.json. Status changes go through states.make_move, so a record can only ever hold a state the
machine allowed, and every move is kept in `moves` with its time, actor and reason.
"""
import json
from datetime import datetime, timezone

from vendor_desk import audit, states
from vendor_desk.states import State


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def path(case_id: str):
    return audit.team_dir() / case_id / "case.json"


def new_case(case_id: str, request_id: str, subject: str = "", requester: str = "", received_at: str = "") -> dict:
    return {
        "case_id": case_id, "request_ids": [request_id], "subject": subject, "requester": requester,
        "received_at": received_at or now(), "updated_at": now(), "status": None, "moves": [],
        "vendor_name": None, "decision": None, "flags": [], "missing_items": [], "checks": [], "reasons": [],
        "reviewer": None, "draft_email": None, "approvals": [], "approvers_required": None,
        "annual_spend_gbp": None, "next_step": "queued", "vendor_id": None, "manager_queue": False,
        "stop_reason": None, "ready_since": None, "injection": False, "raw": {}, "facts": {},
        "usage": {"model_calls": 0, "tool_calls": 0, "tokens": 0, "seconds": 0.0, "cost_usd": 0.0}, "per_role": {},
    }


def load(case_id: str) -> dict | None:
    p = path(case_id)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def save(case: dict) -> None:
    with audit.LOCK:
        case["updated_at"] = now()
        p = path(case["case_id"])
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(case, indent=2, ensure_ascii=False), encoding="utf-8")


def update(case_id: str, fn) -> dict:
    """Load the case, let fn change it, save it: all under one lock so parallel specialists cannot overwrite each other."""
    with audit.LOCK:
        case = load(case_id)
        fn(case)
        save(case)
        return case


def list_cases() -> list[dict]:
    root = audit.team_dir()
    if not root.exists():
        return []
    cases = [json.loads(p.read_text(encoding="utf-8")) for p in root.glob("*/case.json")]
    return sorted(cases, key=lambda c: c["case_id"])


def transition(case: dict, target: State, reason: str, actor: str = "system", by_person: bool = False) -> dict:
    """Move the case (validated by the state machine), record the move on the case and in the audit trail, and save."""
    with audit.LOCK:
        current = State(case["status"]) if case["status"] else None
        move = states.make_move(current, target, reason, actor, by_person)   # raises IllegalMove: nothing is changed
        case["status"] = move.to_state
        case["moves"].append(move.as_dict())
        if move.to_state == State.READY_FOR_APPROVAL.value:
            case["ready_since"] = move.at      # the clock for policy §9 starts when a case starts waiting for approval
            case["manager_queue"] = False
        save(case)
        audit.append(case["case_id"], actor, "state_change",
                     f"{move.from_state or 'new'} -> {move.to_state}: {reason}")
        return case


def add_usage(case: dict, role: str, usage: dict) -> None:
    for k in ("model_calls", "tool_calls", "tokens", "seconds", "cost_usd"):
        case["usage"][k] = round(case["usage"][k] + usage.get(k, 0), 5)
        slot = case["per_role"].setdefault(role, {kk: 0 for kk in ("model_calls", "tool_calls", "tokens", "seconds", "cost_usd")})
        slot[k] = round(slot[k] + usage.get(k, 0), 5)
