"""Diagrams on the fly (Day 2, prompt 10): when a question is about how a system is built, the interviewer draws an architecture diagram for it.

A diagram is Mermaid TEXT (not an image), so code can check it, it is stored with the turn, and the replay can draw it again. Code checks it:
it must start with "flowchart" or "graph", have 4 to 12 nodes and name no real company. A diagram that fails is asked for once more with
the error; if it still fails the question is asked WITHOUT a diagram (a broken diagram never blocks the interview). At most 3 per interview.
The expected points and the weakness are written before the candidate answers, are saved for scoring and review, and are never shown to the candidate.
"""
import re

from pydantic import BaseModel, Field

from app.ai.llm import ModelError, complete_json

MAX_DIAGRAMS = 3
SYSTEM = """You draw one small architecture diagram for an interview question, as Mermaid text.

Rules: start with "flowchart LR" or "graph TD"; use 4 to 12 nodes with short plain labels; show how the parts connect. Name no real company,
product vendor or person: use generic parts (load balancer, app server, database, queue, cache). Also give the description (one or two
sentences), 3 to 5 expected_points a strong answer would make about the diagram, and the one weakness a good candidate should spot."""

REAL_NAMES = re.compile(r"\b(?:google|amazon|aws|microsoft|azure|apple|meta|facebook|netflix|twitter|uber|oracle|ibm|cisco|stripe|paypal|"
                        r"salesforce|openai|anthropic|github|gitlab|cloudflare|akamai|alibaba|tesla|spotify|airbnb|shopify|slack|zoom|"
                        r"mr|mrs|ms|dr|elon|bezos|gates|zuckerberg|jobs)\b", re.I)
HEADER = re.compile(r"^\s*(flowchart|graph)\s+(?:LR|RL|TD|TB|BT)\b", re.I)
EDGE = re.compile(r"-->|---|-\.->|-\.-|==>|--[ox]")
FORCE_DIAGRAM: list[str] = []  # tests only: Mermaid texts the fake returns next (to show a broken one retried, then dropped)


class Diagram(BaseModel):
    title: str
    mermaid: str
    description: str
    expected_points: list[str] = Field(min_length=3, max_length=5)
    weakness: str


def node_ids(mermaid: str) -> set[str]:
    """The distinct node ids in a flowchart (every id that appears on a line with an edge, and every node that is declared)."""
    ids: set[str] = set()
    for line in mermaid.splitlines()[1:]:
        line = line.strip()
        if not line or line.startswith(("%%", "classDef", "style", "linkStyle", "subgraph", "end", "direction")):
            continue
        for part in EDGE.split(re.sub(r"\|[^|]*\|", "", line)):
            m = re.match(r"\s*([A-Za-z_][\w]*)", part)
            if m:
                ids.add(m.group(1))
    return ids


def validate_mermaid(mermaid: str) -> list[str]:
    """Everything wrong with the diagram text. An empty list means it can be drawn."""
    problems = []
    if not HEADER.match(mermaid or ""):
        problems.append('it must start with "flowchart" or "graph" and a direction (for example "flowchart LR")')
    n = len(node_ids(mermaid or ""))
    if not 4 <= n <= 12:
        problems.append(f"it has {n} nodes; it must have 4 to 12")
    hit = REAL_NAMES.search(mermaid or "")
    if hit:
        problems.append(f"it names a real company or person ('{hit.group(0)}'): use generic parts only")
    if re.search(r"<\s*script|javascript:|^\s*click\s", mermaid or "", re.I | re.M):
        problems.append("it contains something that is not a plain diagram")
    return problems


# ---- the rule-based stand-in for the model --------------------------------------------------------------------------------------
def _fake(user: str) -> Diagram:
    if FORCE_DIAGRAM:
        return Diagram(title="Test diagram", mermaid=FORCE_DIAGRAM.pop(0), description="A test.", expected_points=["a", "b", "c"], weakness="w")
    skill = (re.search(r'skill="([^"]*)"', user) or [None, ""])[1].lower()
    if "kubernetes" in skill:
        return Diagram(title="Services on a cluster", description="Traffic enters through an ingress, reaches two copies of a service running as pods, and both read and write one shared database.",
                       mermaid="flowchart LR\n  U[Users] --> I[Ingress]\n  I --> P1[Service pod 1]\n  I --> P2[Service pod 2]\n  P1 --> DB[(Database)]\n  P2 --> DB",
                       expected_points=["the ingress routes traffic to the pods", "pods can be scaled out and replaced", "the single database is a single point of failure",
                                        "a failed pod is restarted by the cluster"],
                       weakness="The single database is a single point of failure.")
    if "pipeline" in skill or "terraform" in skill or "infrastructure" in skill:
        return Diagram(title="A delivery pipeline", description="A change is committed, built and tested, then applied to staging and, after approval, to production.",
                       mermaid="flowchart LR\n  C[Commit] --> B[Build]\n  B --> T[Test]\n  T --> S[Staging]\n  S --> A{Approval}\n  A --> P[Production]",
                       expected_points=["every change is built and tested automatically", "staging is checked before production", "approval is a gate before production",
                                        "a way to roll back is needed"],
                       weakness="There is no rollback step if production fails after approval.")
    return Diagram(title="A small web application", description="Users reach a load balancer, which spreads traffic over two app servers. Both app servers use one database.",
                   mermaid="flowchart LR\n  U[Users] --> LB[Load balancer]\n  LB --> A1[App server 1]\n  LB --> A2[App server 2]\n  A1 --> DB[(Database)]\n  A2 --> DB",
                   expected_points=["the load balancer spreads the traffic", "app servers can be added or removed", "the single database is a single point of failure",
                                    "the database is harder to scale than the app servers"],
                   weakness="The single database is a single point of failure.")


def make_diagram(brief: str, skill: str, candidate_id: int | None = None) -> Diagram | None:
    """A checked diagram for the brief, or None. Asks once more with the error if the first one fails the checks."""
    why = ""
    for _try in range(2):
        retry = f"\n<your_last_diagram_was_rejected_because>{why}</your_last_diagram_was_rejected_because>" if why else ""
        try:
            d = complete_json(SYSTEM, f'<target skill="{skill}" />\n<brief>{brief}</brief>{retry}', Diagram, fake=_fake, task="judgement",
                              agent="diagrams", candidate_id=candidate_id)
        except ModelError as e:
            why = str(e)
            continue
        problems = validate_mermaid(d.mermaid)
        if not problems:
            return d
        why = "; ".join(problems)
    return None
