"""Day 14: a content team of agents that writes IT notices for staff, with a person approving the result.

    supervisor --> researcher   your Day 12 agent: tickets, service status, policies, vendor articles
               --> writer       drafts the notice from the research notes and the style guide
               --> reviewer     checks every claim against the notes; approve or revise
               --> human        a person approves, asks for changes, or rejects
               --> publish      writes the approved notice to outbox/notices/

Every specialist reports back to the supervisor; the supervisor decides who works next.
Handoffs are checked objects from app/handoffs.py. The graph is LangGraph, as on Day 12.

Done: the prompts, the specialists, publish(), build_team() and single_agent_notice().
Activity 2: fill in route().            Check it with tests/test_team_route.py.
Activity 3: fill in human_approval().   Check it with tests/test_human_approval.py.
"""

import json
import operator
import re
from datetime import datetime
from pathlib import Path
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.agent import run_agent
from app.handoffs import (
    HandoffError,
    Notice,
    ResearchNotes,
    Review,
    ask_for,
    parse_handoff,
    schema_for,
)
from app.memory import NoteBook
from app.meter import label
from app.rag import MODEL, llm_client
from app.research_tools import agent_tools

STYLE_GUIDE = "data/Day14_Slide09_notice_style_guide.md"
OUTBOX = "outbox/notices"
MAX_REVISIONS = 2
MAX_STEPS = 12

RESEARCH_TASK = """Research this topic for an IT notice to all staff: {topic}
Find the current facts: the service status, how many related tickets are open (counts only, never
names), what our policies say, and what recent vendor articles say to do.
When you have enough, your final answer must be ONLY one JSON object matching this schema:
{schema}
Every fact needs its source: a tool name, a policy reference or an article id."""

WRITER_PROMPT = """You are the writer in an IT communications team. Write one IT notice for all staff,
using only the facts in the research notes, and following this style guide exactly:

{style}"""

REVIEWER_PROMPT = """You are the reviewer in an IT communications team. Check a draft IT notice
against the research notes and the style guide below.
- Every claim in the notice must be supported by a fact in the notes. List each unsupported claim.
- List every break of the style guide.
- verdict "approve" only if there are no issues; otherwise "revise", with each issue as one short,
  specific instruction to the writer.

{style}"""

SINGLE_TASK = """Write one IT notice for all staff about: {topic}
First research it with your tools: service status, related open tickets (counts only), our
policies, and recent vendor articles. Then follow this style guide exactly:

{style}

Your final answer must be ONLY one JSON object matching this schema:
{schema}"""


class TeamState(TypedDict, total=False):
    topic: str
    research: dict | None
    draft: dict | None
    review: dict | None
    human: dict | None
    revisions: int
    steps: int
    next: str
    status: str
    published_to: str
    handoffs: Annotated[list, operator.add]


def style_guide() -> str:
    return Path(STYLE_GUIDE).read_text(encoding="utf-8")


def handoff(sender: str, receiver: str, summary: str) -> dict:
    return {"handoffs": [{"from": sender, "to": receiver, "summary": summary}]}


# ------------------------------------------------------------------ the specialists
def research(topic: str, client, tools=None, model: str = MODEL) -> ResearchNotes:
    """The researcher is the Day 12 agent, asked to finish with a ResearchNotes object."""
    label(client, "researcher")
    tools = tools if tools is not None else agent_tools(NoteBook())
    task = RESEARCH_TASK.format(topic=topic, schema=schema_for(ResearchNotes))
    run = run_agent(task, client=client, model=model, tools=tools)
    try:
        return parse_handoff(run["answer"], ResearchNotes)
    except HandoffError:  # one repair attempt, without tools
        return ask_for(
            client,
            model,
            "Turn research findings into JSON.",
            run["answer"],
            ResearchNotes,
        )


def write(
    notes: ResearchNotes, client, feedback: list[str] | None = None, model: str = MODEL
) -> Notice:
    label(client, "writer")
    user = "Research notes:\n" + notes.model_dump_json(indent=1)
    if feedback:
        user += "\n\nRevise your notice. Fix every point:\n- " + "\n- ".join(feedback)
    return ask_for(
        client, model, WRITER_PROMPT.format(style=style_guide()), user, Notice
    )


def review(notes: ResearchNotes, notice: Notice, client, model: str = MODEL) -> Review:
    label(client, "reviewer")
    user = (
        "Research notes:\n"
        + notes.model_dump_json(indent=1)
        + "\n\nDraft notice:\n"
        + notice.model_dump_json(indent=1)
    )
    return ask_for(
        client, model, REVIEWER_PROMPT.format(style=style_guide()), user, Review
    )


# ------------------------------------------------------------------ Activity 2: the supervisor's rule
def route(state: dict) -> str:
    """Decide who works next. Returns "researcher", "writer", "reviewer", "human",
    "publish" or "end".

    Rules, checked in this order (tests/test_team_route.py checks each one):
    1. state has a "status" (published, rejected or stopped)        -> "end"
    2. state["steps"] (default 0) is more than MAX_STEPS            -> "end"
    3. no "research" yet                                            -> "researcher"
    4. no "draft" yet                                               -> "writer"
    5. no "review" yet                                              -> "reviewer"
    6. review verdict is "revise" and revisions (default 0) < MAX_REVISIONS -> "writer"
    7. no "human" decision yet                                      -> "human"
    8. human decision is "approve"                                  -> "publish"
    9. human decision is "revise" and revisions < MAX_REVISIONS     -> "writer"
    10. anything else                                               -> "end"
    A missing key and a key set to None both count as "not yet".
    """
    if state.get("status"):
        return "end"
    if (state.get("steps") or 0) > MAX_STEPS:
        return "end"
    if not state.get("research"):
        return "researcher"
    if not state.get("draft"):
        return "writer"
    if not state.get("review"):
        return "reviewer"
    revisions = state.get("revisions") or 0
    if state["review"].get("verdict") == "revise" and revisions < MAX_REVISIONS:
        return "writer"
    if not state.get("human"):
        return "human"
    decision = state["human"].get("decision")
    if decision == "approve":
        return "publish"
    if decision == "revise" and revisions < MAX_REVISIONS:
        return "writer"
    return "end"


# ------------------------------------------------------------------ Activity 3: the person
def human_approval(state: dict) -> dict:
    """Pause the team and ask a person to approve the draft.

    Rules (tests/test_human_approval.py checks each one):
    - answer = interrupt({"question": "Publish this notice? approve, revise or reject",
                          "draft": state["draft"], "review": state["review"]})
      (LangGraph stops here and saves the state; the run carries on when someone resumes it with
       Command(resume={"decision": ..., "comment": ...}), and answer is that dict)
    - decision = answer["decision"], lower case and stripped; comment = answer.get("comment", "")
      if answer is not a dict, or the decision is not approve, revise or reject: decision = "reject"
      (anything unclear is a no)
    - return {"human": {"decision": decision, "comment": comment},
              **handoff("human", "supervisor", f"{decision}: {comment}")}
      and also "status": "rejected" when the decision is reject
    Do not put interrupt() inside try/except: it works by raising a special exception.
    Until you finish it, nobody is asked and nothing is published.
    """
    answer = interrupt(
        {
            "question": "Publish this notice? approve, revise or reject",
            "draft": state["draft"],
            "review": state["review"],
        }
    )
    decision, comment = "reject", ""
    if isinstance(answer, dict):
        comment = answer.get("comment", "")
        said = str(answer.get("decision", "")).lower().strip()
        if said in ("approve", "revise", "reject"):
            decision = said
    update = {
        "human": {"decision": decision, "comment": comment},
        **handoff("human", "supervisor", f"{decision}: {comment}"),
    }
    if decision == "reject":
        update["status"] = "rejected"
    return update


# ------------------------------------------------------------------ publishing
def today() -> str:
    return datetime.now().astimezone().date().isoformat()


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:50] or "notice"


def notice_markdown(notice: dict, comment: str = "") -> str:
    lines = [
        f"# {notice['title']}",
        "",
        f"For: {notice['audience']}",
        "",
        notice["body"],
        "",
    ]
    if notice.get("actions"):
        lines += ["What to do:"] + [f"- {a}" for a in notice["actions"]] + [""]
    if notice.get("sources"):
        lines += ["Sources: " + ", ".join(notice["sources"]), ""]
    lines.append(
        f"Approved by a person on {today()}" + (f": {comment}" if comment else "")
    )
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ the team
def writer_feedback(state: dict) -> list[str]:
    """What the writer must fix: the reviewer's issues and the person's comment."""
    feedback = []
    if state.get("review") and state["review"]["verdict"] == "revise":
        feedback += state["review"]["issues"]
    if state.get("human") and state["human"].get("decision") == "revise":
        feedback.append(
            "From the person approving: " + state["human"].get("comment", "")
        )
    return feedback


def build_team(
    client=None,
    tools=None,
    checkpointer=None,
    model: str = MODEL,
    route_fn=route,
    extra_nodes: dict | None = None,
    outbox: str = OUTBOX,
    state_schema=TeamState,
    feedback_fn=writer_feedback,
):
    """The team as a LangGraph graph.

    For the homework you can add a specialist without changing this function: pass its node in
    extra_nodes, your own route_fn that sends work to it, a state_schema with its extra key, and a
    feedback_fn if the writer must see what it found."""
    client = client or llm_client()

    def supervisor(state):
        steps = (state.get("steps") or 0) + 1
        nxt = route_fn({**state, "steps": steps})
        update = {
            "steps": steps,
            "next": nxt,
            **handoff("supervisor", nxt, f"step {steps}"),
        }
        if nxt == "end" and not state.get("status"):
            update["status"] = "stopped: " + (
                "step limit" if steps > MAX_STEPS else "no approval"
            )
        return update

    def researcher(state):
        try:
            notes = research(state["topic"], client, tools, model)
        except HandoffError as e:
            return {"status": f"stopped: researcher handoff failed: {e}"}
        return {
            "research": notes.model_dump(),
            **handoff("researcher", "supervisor", f"{len(notes.facts)} facts"),
        }

    def writer(state):
        feedback = feedback_fn(state)
        try:
            notice = write(ResearchNotes(**state["research"]), client, feedback, model)
        except HandoffError as e:
            return {"status": f"stopped: writer handoff failed: {e}"}
        words = len(notice.body.split())
        return {
            "draft": notice.model_dump(),
            "review": None,
            "human": None,
            "revisions": (state.get("revisions") or 0)
            + (1 if state.get("draft") else 0),
            **handoff(
                "writer", "supervisor", f'draft "{notice.title}" ({words} words)'
            ),
        }

    def reviewer(state):
        try:
            verdict = review(
                ResearchNotes(**state["research"]),
                Notice(**state["draft"]),
                client,
                model,
            )
        except HandoffError as e:
            return {"status": f"stopped: reviewer handoff failed: {e}"}
        return {
            "review": verdict.model_dump(),
            **handoff(
                "reviewer",
                "supervisor",
                f"{verdict.verdict}, {len(verdict.issues)} issues",
            ),
        }

    def publish(state):
        path = Path(outbox) / f"{today()}-{slug(state['draft']['title'])}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            notice_markdown(state["draft"], state["human"].get("comment", "")),
            encoding="utf-8",
        )
        return {
            "status": "published",
            "published_to": str(path),
            **handoff("publish", "supervisor", str(path)),
        }

    nodes = {
        "researcher": researcher,
        "writer": writer,
        "reviewer": reviewer,
        "human": human_approval,
        "publish": publish,
        **(extra_nodes or {}),
    }
    graph = StateGraph(state_schema)
    graph.add_node("supervisor", supervisor)
    for name, fn in nodes.items():
        graph.add_node(name, fn)
        graph.add_edge(name, "supervisor")
    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor", lambda s: s["next"], {**{n: n for n in nodes}, "end": END}
    )
    return graph.compile(checkpointer=checkpointer)


# ------------------------------------------------------------------ one agent doing everything
def single_agent_notice(
    topic: str, client=None, tools=None, model: str = MODEL
) -> Notice:
    """The comparison: the Day 12 agent researches and writes the notice on its own."""
    client = client or llm_client()
    label(client, "single agent")
    tools = tools if tools is not None else agent_tools(NoteBook())
    task = SINGLE_TASK.format(
        topic=topic, style=style_guide(), schema=schema_for(Notice)
    )
    run = run_agent(task, client=client, model=model, tools=tools)
    try:
        return parse_handoff(run["answer"], Notice)
    except HandoffError:
        return ask_for(
            client, model, "Turn this IT notice into JSON.", run["answer"], Notice
        )


def show(obj) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)
