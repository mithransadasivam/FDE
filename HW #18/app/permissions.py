"""Day 17: least privilege for the agent. Give each agent only the tools its job needs.

all_tools() is the agent "as a colleague set it up in a hurry": every Day 11 and Day 12 tool,
update_ticket with the approval step switched off, and run_sql, which runs any SQL at all on the
help desk database, staff table included. That is excessive agency (OWASP LLM03:2026): if the
agent is tricked, everything it is allowed to do can be done to you.

Done: run_sql(), all_tools(), agent_toolset(), guarded_tools() and the PERMISSIONS list.
Activity 4: fill in restrict_tools(). Check it with tests/test_permissions.py.
"""

import os
import sqlite3
from dataclasses import replace

from app.guardrails import screen_value
from app.memory import NoteBook
from app.research_tools import agent_tools
from app.tools import TOOLS, Tool

# Which tools each agent may use. "allow": it may call them. "approve": it may call them, but
# only after a person approves each call (Day 11's approve_and_run()).
PERMISSIONS = {
    "research_agent": {
        "allow": [
            "calculate",
            "service_status",
            "find_tickets",
            "get_ticket",
            "search_policies",
            "web_search",
            "read_article",
            "save_note",
            "read_notes",
        ],
        "approve": [],
    },
    "service_desk_assistant": {
        "allow": ["service_status", "find_tickets", "get_ticket", "search_policies"],
        "approve": ["update_ticket"],
    },
}


def sql_db() -> str:
    from app import tools

    return tools.DB_PATH


def run_sql(sql: str) -> dict:
    """DANGEROUS, on purpose: any SQL, on an ordinary (writable) connection, all columns."""
    with sqlite3.connect(sql_db()) as con:
        cur = con.execute(sql)
        rows = cur.fetchmany(50) if cur.description else []
        columns = [d[0] for d in cur.description] if cur.description else []
        return {"columns": columns, "rows": rows, "changed": con.total_changes}


RUN_SQL_SCHEMA = {
    "name": "run_sql",
    "description": "Run an SQL statement on the help desk database (tables: tickets, assets, staff).",
    "parameters": {
        "type": "object",
        "properties": {
            "sql": {"type": "string", "description": "The SQL statement to run."}
        },
        "required": ["sql"],
        "additionalProperties": False,
    },
}


def all_tools(notebook: NoteBook) -> dict:
    """Every tool, with update_ticket's approval switched off, plus run_sql. Do not ship this."""
    tools = agent_tools(notebook)
    tools["update_ticket"] = replace(TOOLS["update_ticket"], changes_data=False)
    tools["run_sql"] = Tool(run_sql, RUN_SQL_SCHEMA)
    return tools


def restrict_tools(tools: dict, role: str) -> dict:
    """TODO (Activity 4): only the tools this role's PERMISSIONS entry names.

    Rules (tests/test_permissions.py checks each one):
    - an unknown role raises KeyError (no permissions entry means no tools, never all tools)
    - the result is a NEW dict: never change the tools dict you were given
    - a name in the role's "allow" list that is in tools: keep that Tool as it is
    - a name in the role's "approve" list that is in tools: keep it, but always with
      changes_data=True, so every call waits for a person (use dataclasses.replace)
    - a listed name that is not in tools is skipped; every tool not listed is left out
    """
    entry = PERMISSIONS[role]  # an unknown role raises KeyError
    kept = {}
    for name in entry["allow"]:
        if name in tools:
            kept[name] = tools[name]
    for name in entry["approve"]:
        if name in tools:
            kept[name] = replace(tools[name], changes_data=True)
    return kept


def agent_toolset(profile: str, notebook: NoteBook) -> dict:
    """ "wide": all_tools(). "least": the research agent's permissions only."""
    tools = all_tools(notebook)
    return tools if profile == "wide" else restrict_tools(tools, "research_agent")


def guarded_tools(tools: dict) -> dict:
    """The same tools, but every result passes the content guardrail first: text that talks to
    the AI is replaced before the model reads it."""

    def guard(fn):
        return lambda **args: screen_value(fn(**args))

    return {name: replace(t, fn=guard(t.fn)) for name, t in tools.items()}


AGENT_PROFILE = os.getenv("AGENT_PROFILE", "wide")
