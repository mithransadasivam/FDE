"""Activity 2 (ticket ENG-202): check a candidate architecture against the client's rules.

Each option is a JSON file in docs/architecture/. The rules come from discovery (Day 1): Helen's
constraints and Tom's note that CaseFlow is read-only. Writing them as code means every option,
and every later change, is checked the same way.
"""

import json
from typing import Literal, Optional

from pydantic import BaseModel

from app.config import ARCHITECTURE_DIR

Kind = Literal["person", "ui", "service", "model", "ocr", "store", "system", "audit_log", "decision"]


class Node(BaseModel):
    id: str
    label: str
    kind: Kind
    lane: Literal["client", "bank", "aws", "external"]
    row: int
    region: str = "uk"
    hosting: str = ""
    customer_data: bool = False
    read_only: bool = False


class Edge(BaseModel):
    model_config = {"populate_by_name": True}
    source: str = ""
    target: str = ""
    label: str = ""

    def __init__(self, **data):
        data.setdefault("source", data.pop("from", ""))
        data.setdefault("target", data.pop("to", ""))
        super().__init__(**data)


class Architecture(BaseModel):
    id: str
    name: str
    summary: str
    time_to_pilot_weeks: float
    strengths: list[str] = []
    weaknesses: list[str] = []
    cost: dict
    nodes: list[Node]
    edges: list[Edge]


class Violation(BaseModel):
    rule: Literal["residency", "public_ai", "read_only", "human_decides", "audit"]
    message: str
    node: Optional[str] = None
    edge: Optional[list[str]] = None  # [source, target]


RULES = [
    ("residency", "Customer data stays in the UK", "Helen"),
    ("public_ai", "No public AI services", "Helen"),
    ("read_only", "Only people write to CaseFlow; its API is read-only", "Tom"),
    ("human_decides", "A person makes every KYC decision", "Helen"),
    ("audit", "Every model call is logged", "Helen"),
]


def load_options() -> list[Architecture]:
    return [Architecture(**json.loads(p.read_text(encoding="utf-8"))) for p in sorted(ARCHITECTURE_DIR.glob("option_*.json"))]


def check_architecture(arch: Architecture) -> list[Violation]:
    """Return every way arch breaks the client's rules, grouped by rule in RULES order, and
    within a rule in the order the nodes or edges appear in the file.

    - residency: a node with customer_data whose region is not "uk".
      message: f"Customer data leaves the UK at {label}", node=id
    - public_ai: a node of kind "model" with hosting "public".
      message: f"{label} is a public AI service", node=id
    - read_only: an edge into a read_only node from a node that is not a person.
      message: f"{source label} writes to {target label}", edge=[source, target]
    - human_decides: (1) each edge from a "model" node into a "decision" node:
      message: f"{model label} makes the decision", edge=[source, target];
      (2) then, if no edge goes from a "person" node into a "decision" node:
      message: "No person makes the decision", with no node or edge
    - audit: a "model" node with no edge to an "audit_log" node.
      message: f"{label} is not logged", node=id
    An empty list means the option meets every rule.
    """
    by_id = {n.id: n for n in arch.nodes}
    out: list[Violation] = []
    for n in arch.nodes:
        if n.customer_data and n.region != "uk":
            out.append(Violation(rule="residency", message=f"Customer data leaves the UK at {n.label}", node=n.id))
    for n in arch.nodes:
        if n.kind == "model" and n.hosting == "public":
            out.append(Violation(rule="public_ai", message=f"{n.label} is a public AI service", node=n.id))
    for e in arch.edges:
        s, t = by_id.get(e.source), by_id.get(e.target)
        if s and t and t.read_only and s.kind != "person":
            out.append(Violation(rule="read_only", message=f"{s.label} writes to {t.label}", edge=[e.source, e.target]))
    for e in arch.edges:
        s, t = by_id.get(e.source), by_id.get(e.target)
        if s and t and s.kind == "model" and t.kind == "decision":
            out.append(Violation(rule="human_decides", message=f"{s.label} makes the decision", edge=[e.source, e.target]))
    if not any(by_id.get(e.source) and by_id.get(e.target) and by_id[e.source].kind == "person"
               and by_id[e.target].kind == "decision" for e in arch.edges):
        out.append(Violation(rule="human_decides", message="No person makes the decision"))
    for n in arch.nodes:
        if n.kind == "model" and not any(e.source == n.id and by_id.get(e.target) and by_id[e.target].kind == "audit_log" for e in arch.edges):
            out.append(Violation(rule="audit", message=f"{n.label} is not logged", node=n.id))
    return out
