"""The supervisor as a LangGraph graph: it moves each candidate along the pipeline, runs the automatic steps itself, and STOPS at an
approval gate (a LangGraph interrupt) wherever a person must decide. The graph is checkpointed in SQLite, so a candidate's progress
survives a restart and resumes at the same gate. Every move still goes through app/supervisor.move(), which refuses anything the table
of allowed moves does not permit, and writes it to the decision log.

    graph = SupervisorAgent(db).run(candidate_id)            # advances automatic steps, then waits at a gate
    SupervisorAgent(db).approve(candidate_id, "r@x.com", "reason")   # a person decides: the graph resumes and makes that move
"""
import sqlite3
from contextvars import ContextVar
from pathlib import Path
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.base import BaseAgent, register_tool
from app.config import get_settings
from app.models import Candidate, DecisionLog
from app.schemas import Stage
from app.supervisor import ALLOWED, MoveRefused, move

_db: ContextVar[Session | None] = ContextVar("supervisor_db", default=None)

# the gate a person must pass at each stage, and where an approval leads
GATES = {
    Stage.REVIEW: ("recruiter checks the unsure fields", Stage.EXTRACTED),
    Stage.SCREENED: ("recruiter approves the shortlist", Stage.SHORTLISTED),
    Stage.SHORTLISTED: ("recruiter invites to the AI interview", Stage.AI_INTERVIEW),
    Stage.AI_INTERVIEW: ("recruiter reviews the scorecard and moves to the human interview", Stage.HUMAN_INTERVIEW),
    Stage.HUMAN_INTERVIEW: ("recruiter decides", Stage.DECISION),
}


class State(TypedDict, total=False):
    candidate_id: int
    stage: str
    waiting_for: str
    note: str


def _cand(state: State) -> Candidate:
    return _db.get().get(Candidate, state["candidate_id"])


def routing_rule(stage: str) -> str:
    """The routing rule in code: which node handles a candidate in this stage."""
    s = Stage(stage)
    if s == Stage.APPLIED:
        return "read_cv"
    if s == Stage.EXTRACTED:
        return "screen"
    if s in GATES:
        return "gate"
    return "done"


def n_route(state: State) -> State:
    c = _cand(state)
    return {**state, "stage": c.stage}


def n_read_cv(state: State) -> State:
    """The document agent reads CVs in a background task after the apply page replies; the supervisor just waits for it."""
    return {**state, "waiting_for": "document agent is reading the CV", "note": "automatic step pending"}


def n_screen(state: State) -> State:
    """EXTRACTED -> SCREENED is an automatic step the system may make, once the rubric is approved."""
    from app.agents.screening import ScreeningAgent, save_scores
    from app.models import Requisition

    db, c = _db.get(), _cand(state)
    req = db.get(Requisition, c.requisition_id)
    if req.status not in ("APPROVED", "PUBLISHED"):
        return {**state, "waiting_for": "hiring manager approves the rubric", "note": "cannot score before the rubric is approved"}
    result = ScreeningAgent(db, c.id).run(db, c, req)
    save_scores(db, req, result)
    move(db, c, Stage.SCREENED, "system", f"scored against the approved rubric: {result.weighted_total}/100",
         evidence={"weighted_total": result.weighted_total})
    db.commit()
    return {**state, "stage": c.stage, "note": f"scored {result.weighted_total}/100"}


def n_gate(state: State) -> State:
    """Stops for a person. Resumes with {"approved": bool, "actor": email, "reason": text}; only then is the move made."""
    db, c = _db.get(), _cand(state)
    what, target = GATES[Stage(c.stage)]
    answer = interrupt({"gate": what, "stage": c.stage, "next": target.value})
    if answer.get("approved"):
        try:
            move(db, c, target, answer.get("actor", ""), answer.get("reason", ""), evidence=answer.get("evidence"))
            db.commit()
        except MoveRefused as e:
            db.rollback()
            return {**state, "note": f"refused: {e}", "waiting_for": what}
    return {**state, "stage": c.stage}


def after_route(state: State) -> str:
    return routing_rule(state["stage"])


def after_step(state: State) -> str:
    """After an automatic step or a gate: stop if still waiting on someone, otherwise route again."""
    return "end" if state.get("waiting_for") else "route"


def build_graph(checkpointer):
    g = StateGraph(State)
    for name, fn in (("route", n_route), ("read_cv", n_read_cv), ("screen", n_screen), ("gate", n_gate)):
        g.add_node(name, fn)
    g.set_entry_point("route")
    g.add_conditional_edges("route", after_route, {"read_cv": "read_cv", "screen": "screen", "gate": "gate", "done": END})
    g.add_edge("read_cv", END)
    g.add_conditional_edges("screen", after_step, {"end": END, "route": "route"})
    g.add_conditional_edges("gate", after_step, {"end": END, "route": "route"})
    return g.compile(checkpointer=checkpointer)


_saver: SqliteSaver | None = None


def checkpointer() -> SqliteSaver:
    global _saver
    if _saver is None:
        path = Path(get_settings().storage_dir) / "supervisor.db"
        path.parent.mkdir(parents=True, exist_ok=True)
        _saver = SqliteSaver(sqlite3.connect(str(path), check_same_thread=False))
    return _saver


# ---- tools ----------------------------------------------------------------------------------------------------------------------------
class RuleArgs(BaseModel):
    stage: str


class CheckpointArgs(BaseModel):
    candidate_id: int


class LogArgs(BaseModel):
    limit: int = 20


@register_tool("routing_rule", RuleArgs, "Which handler a candidate in this stage goes to, and who may move them on")
def t_routing_rule(args: RuleArgs, ctx: dict) -> dict:
    s = Stage(args.stage)
    return {"handler": routing_rule(args.stage), "allowed": {t.value: who for t, who in ALLOWED[s].items()}, "gate": GATES[s][0] if s in GATES else None}


@register_tool("checkpoint", CheckpointArgs, "The saved supervisor state of a candidate (resumes after a restart)")
def t_checkpoint(args: CheckpointArgs, ctx: dict) -> dict:
    snap = build_graph(checkpointer()).get_state({"configurable": {"thread_id": f"candidate-{args.candidate_id}"}})
    return {"values": dict(snap.values or {}), "next": list(snap.next or []), "waiting": [i.value for t in snap.tasks for i in t.interrupts]}


@register_tool("decision_log", LogArgs, "Read the latest decision log entries")
def t_decision_log(args: LogArgs, ctx: dict) -> list[dict]:
    rows = ctx["db"].scalars(select(DecisionLog).order_by(DecisionLog.id.desc()).limit(args.limit)).all()
    return [{"actor": r.actor, "action": r.action, "subject": r.subject, "reason": r.reason} for r in rows]


class SupervisorAgent(BaseAgent):
    name = "supervisor"

    def _config(self, cid: int) -> dict:
        return {"configurable": {"thread_id": f"candidate-{cid}"}}

    def run(self, candidate_id: int) -> dict:
        """Advances the automatic steps and stops at the next gate. Returns what it is waiting for."""
        token = _db.set(self.db)
        try:
            graph = build_graph(checkpointer())
            cfg = self._config(candidate_id)
            snap = graph.get_state(cfg)
            if snap.next:  # already paused at a gate: report it rather than starting again
                return self._report(graph, cfg)
            graph.invoke({"candidate_id": candidate_id}, cfg)
            return self._report(graph, cfg)
        finally:
            _db.reset(token)

    def approve(self, candidate_id: int, actor: str, reason: str, approved: bool = True, evidence: dict | None = None) -> dict:
        """A person passes the gate. The graph resumes and makes that move (or refuses it), then stops at the next gate."""
        token = _db.set(self.db)
        try:
            graph = build_graph(checkpointer())
            cfg = self._config(candidate_id)
            graph.invoke(Command(resume={"approved": approved, "actor": actor, "reason": reason, "evidence": evidence}), cfg)
            return self._report(graph, cfg)
        finally:
            _db.reset(token)

    def _report(self, graph, cfg) -> dict:
        snap = graph.get_state(cfg)
        waiting = [i.value for t in snap.tasks for i in t.interrupts]
        values = dict(snap.values or {})
        return {"stage": values.get("stage"), "waiting_at_gate": waiting[0] if waiting else None, "waiting_for": values.get("waiting_for"),
                "note": values.get("note")}


def reset_checkpoints() -> None:
    """Forget every saved supervisor thread (used by tests and by the demo's --reset)."""
    global _saver
    if _saver is not None:
        for table in ("checkpoints", "writes"):
            try:
                _saver.conn.execute(f"DELETE FROM {table}")
            except Exception:
                pass
        _saver.conn.commit()
