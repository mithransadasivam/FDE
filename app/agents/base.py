"""The agent framework: every agent has a narrow job, its own tools and nothing else (least privilege), a step limit and a trace.

A tool is a registered function with a Pydantic model for its arguments (so it has a JSON Schema and checked arguments).
An agent can only call the tools listed for it in AGENT_TOOLS, which is the table in section 12 of the brief.
"""
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel

from app.tracing import span

# Section 12 of the brief: which tools each agent may use. Anything else is refused by code, not by a prompt.
AGENT_TOOLS: dict[str, frozenset[str]] = {
    "supervisor": frozenset({"routing_rule", "checkpoint", "decision_log"}),
    "requisition": frozenset({"transcribe", "wording_check", "save_rubric"}),
    "document": frozenset({"read_pdf", "read_docx", "read_image", "find_duplicate"}),
    "screening": frozenset({"search_cvs", "score_item"}),
    "interviewer": frozenset({"speak", "show_diagram", "listen", "give_hint", "score_answer", "end_interview"}),
    "copilot": frozenset({"transcribe_stream", "mark_point", "suggest_question", "flag_cv_conflict", "coverage"}),
    "assistant": frozenset({"search_cvs", "search_policy", "list_requisitions", "get_candidate", "search_candidates"}),
    "communications": frozenset({"draft_email", "find_slot"}),
    "compliance": frozenset({"check_evidence", "scan_prompt_log", "check_log"}),
}
STEP_LIMITS = {"supervisor": 50, "requisition": 10, "document": 10, "screening": 40, "interviewer": 60, "copilot": 400, "assistant": 12,
               "communications": 10, "compliance": 80}


class ToolDenied(Exception):
    """The agent tried to use a tool that is not in its row of the table."""


class StepLimitExceeded(Exception):
    """The agent used more steps than its limit allows."""


@dataclass
class Tool:
    name: str
    args_model: type[BaseModel]
    fn: Callable[[Any, dict], Any]
    description: str = ""

    def schema(self) -> dict:
        return {"name": self.name, "description": self.description, "parameters": self.args_model.model_json_schema()}


TOOLS: dict[str, Tool] = {}


def register_tool(name: str, args_model: type[BaseModel], description: str = ""):
    """Decorator: register fn(args, ctx) as a tool. The arguments are validated against args_model before it runs."""
    def wrap(fn):
        TOOLS[name] = Tool(name, args_model, fn, description or (fn.__doc__ or "").strip().split("\n")[0])
        return fn
    return wrap


class BaseAgent:
    name = "agent"
    step_limit = 20

    def __init__(self, db=None, candidate_id: int | None = None, **ctx):
        self.db = db
        self.ctx: dict = {"db": db, "candidate_id": candidate_id, **ctx}
        self.candidate_id = candidate_id
        self.steps = 0
        self.denied: list[str] = []
        self.step_limit = STEP_LIMITS.get(self.name, self.step_limit)

    @property
    def allowed_tools(self) -> frozenset[str]:
        return AGENT_TOOLS.get(self.name, frozenset())

    def tool_schemas(self) -> list[dict]:
        """The JSON Schemas of the tools this agent may use (what a real model would be shown)."""
        return [TOOLS[t].schema() for t in sorted(self.allowed_tools) if t in TOOLS]

    def call(self, tool: str, **kwargs):
        if tool not in self.allowed_tools:
            self.denied.append(tool)
            with span(self.name, f"DENIED {tool}", self.candidate_id):
                pass
            raise ToolDenied(f"The {self.name} agent is not allowed to use the tool '{tool}'")
        self.steps += 1
        if self.steps > self.step_limit:
            raise StepLimitExceeded(f"The {self.name} agent used more than {self.step_limit} steps")
        if tool not in TOOLS:
            from app import tools
            tools.load()
        t = TOOLS[tool]
        args = t.args_model(**kwargs)  # checked arguments
        with span(self.name, tool, self.candidate_id):
            return t.fn(args, self.ctx)
