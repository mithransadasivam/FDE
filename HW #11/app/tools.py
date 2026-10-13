"""Day 11: the tools the assistant can use, and the schemas that describe them to the model.

Each tool is a plain Python function plus a schema: the name, a description and the arguments,
written as JSON Schema. The model only ever sees the schema. Your code runs the function.

Done: calculate, service_status, find_tickets (the function), get_ticket, update_ticket,
search_policies and their schemas, except one.
Activity 2: write FIND_TICKETS_SCHEMA. Check it with tests/test_tool_schemas.py.
"""

import ast
import json
import operator
import os
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
DB_PATH = os.getenv("HELPDESK_DB", "data/helpdesk.db")
STATUS_FILE = "data/Day11_Slide09_service_status.json"
ACTIONS_LOG = "logs/actions.jsonl"
SERVICES = [
    "SecureLink VPN",
    "Company Mail",
    "Print Queue",
    "Wi-Fi",
    "Finance Portal",
    "Backup Agent",
]
STATUSES = ["open", "in_progress", "closed"]
DEVICE_TYPES = ["laptop", "desktop", "monitor", "docking station", "phone"]
TEAMS = ["service desk", "network team", "end-user team"]
SEVERITIES = ["P1", "P2", "P3", "P4"]


# ------------------------------------------------------------------ the functions
_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def calculate(expression: str) -> dict:
    """Work out an arithmetic expression such as "12 * 7.5 * 12". Numbers and + - * / % ** ( ) only:
    never eval(), so the model cannot run code through this tool."""

    def ev(node):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, (int, float))
            and not isinstance(node.value, bool)
        ):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            left, right = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 10:
                raise ValueError("powers above 10 are not allowed")
            return _OPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](ev(node.operand))
        raise ValueError("only numbers and + - * / % ** ( ) are allowed")

    if len(expression) > 200:
        raise ValueError("the expression is too long")
    value = ev(ast.parse(expression, mode="eval").body)
    return {"expression": expression, "result": round(value, 4)}


def service_status(service: str, status_file: str = STATUS_FILE) -> dict:
    """The current status of one IT service: operational, degraded or outage."""
    statuses = json.loads(Path(status_file).read_text(encoding="utf-8"))
    if service not in statuses:
        raise ValueError(
            f"unknown service {service!r}; known services: {', '.join(statuses)}"
        )
    return {"service": service, **statuses[service]}


def _read_only(db_path):
    # mode=ro: this connection cannot change the database, whatever SQL reaches it
    return sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro", uri=True)


def find_tickets(
    status=None, application=None, severity=None, limit=10, db_path=None
) -> dict:
    """Search the tickets. Every filter is optional. Returns the number found and the first `limit`."""
    where, params = [], []
    for column, value in (
        ("status", status),
        ("application", application),
        ("severity", severity),
    ):
        if value is not None:
            where.append(
                f"{column} = ?"
            )  # the column names are fixed here; values go in as parameters
            params.append(value)
    sql = " FROM tickets" + (" WHERE " + " AND ".join(where) if where else "")
    with _read_only(db_path or DB_PATH) as con:
        count = con.execute("SELECT COUNT(*)" + sql, params).fetchone()[0]
        rows = con.execute(
            "SELECT id, created, application, error_code, severity, status, summary"
            + sql
            + " ORDER BY created DESC LIMIT ?",
            [*params, int(limit)],
        ).fetchall()
    keys = [
        "id",
        "created",
        "application",
        "error_code",
        "severity",
        "status",
        "summary",
    ]
    return {"count": count, "tickets": [dict(zip(keys, r)) for r in rows]}


def find_assets(
    assigned_to=None, department=None, device_type=None, db_path=None
) -> dict:
    """List devices from the assets table. At least one filter is required."""
    if not (assigned_to or department or device_type):
        raise ValueError("give at least one of assigned_to, department or device_type")
    where, params = [], []
    for column, value in (
        ("assigned_to", assigned_to),
        ("department", department),
        ("device_type", device_type),
    ):
        if value is not None:
            where.append(f"{column} = ?")  # fixed column names; values as parameters
            params.append(value)
    keys = [
        "asset_tag",
        "device_type",
        "model",
        "assigned_to",
        "department",
        "purchase_date",
    ]
    with _read_only(db_path or DB_PATH) as con:
        rows = con.execute(
            f"SELECT {', '.join(keys)} FROM assets WHERE "
            + " AND ".join(where)
            + " ORDER BY asset_tag",
            params,
        ).fetchall()
    return {"count": len(rows), "assets": [dict(zip(keys, r)) for r in rows]}


def get_ticket(ticket_id: str, db_path=None) -> dict:
    """One ticket, with its notes."""
    with _read_only(db_path or DB_PATH) as con:
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM tickets WHERE id = ?", [ticket_id]).fetchone()
    if row is None:
        raise ValueError(f"no ticket with id {ticket_id}")
    return dict(row)


def update_ticket(ticket_id: str, status: str, note: str, db_path=None) -> dict:
    """CHANGES DATA: set a ticket's status and add a note. Only ever run after the user approves."""
    with sqlite3.connect(db_path or DB_PATH) as con:
        old = con.execute(
            "SELECT status, notes FROM tickets WHERE id = ?", [ticket_id]
        ).fetchone()
        if old is None:
            raise ValueError(f"no ticket with id {ticket_id}")
        stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
        notes = ((old[1] or "") + f"\n[{stamp}] {note}").strip()
        con.execute(
            "UPDATE tickets SET status = ?, notes = ? WHERE id = ?",
            [status, notes, ticket_id],
        )
    return {"id": ticket_id, "old_status": old[0], "new_status": status}


def assign_ticket(ticket_id: str, team: str, db_path=None) -> dict:
    """CHANGES DATA: give an open ticket to a team. Only ever run after the user approves."""
    if team not in TEAMS:
        raise ValueError(f"unknown team {team!r}; the teams are: {', '.join(TEAMS)}")
    with sqlite3.connect(db_path or DB_PATH) as con:
        old = con.execute(
            "SELECT assignee, status FROM tickets WHERE id = ?", [ticket_id]
        ).fetchone()
        if old is None:
            raise ValueError(f"no ticket with id {ticket_id}")
        if old[1] == "closed":
            raise ValueError(f"{ticket_id} is closed; reopen it first")
        con.execute("UPDATE tickets SET assignee = ? WHERE id = ?", [team, ticket_id])
    return {"id": ticket_id, "old_assignee": old[0] or "nobody", "new_assignee": team}


def search_policies(question: str, retriever: Callable | None = None) -> dict:
    """Search the IT policy documents (the Days 6–7 index). Returns numbered sources to cite."""
    from app.rag import MIN_SCORE

    if retriever is None:
        from app.advanced import RAG_MODE, retrieve

        def retriever(q):
            return retrieve(q, mode=RAG_MODE)["chunks"]

    kept = [c for c in retriever(question) if c["score"] >= MIN_SCORE]
    if not kept:
        return {
            "found": False,
            "sources": [],
            "note": "Nothing in the IT policies matches. Say you don't know.",
        }
    return {
        "found": True,
        "sources": [
            {"ref": f"[{i}] {c['source']}, page {c['page']}", "text": c["text"]}
            for i, c in enumerate(kept, 1)
        ],
    }


# ------------------------------------------------------------------ the schemas the model sees
CALCULATE_SCHEMA = {
    "name": "calculate",
    "description": "Work out an arithmetic expression exactly, for example costs, totals or percentages. "
    "Use it for every calculation instead of doing the arithmetic yourself.",
    "parameters": {
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "maxLength": 200,
                "description": 'Numbers and + - * / % ** ( ) only, for example "12 * 7.5 * 12"',
            },
        },
        "required": ["expression"],
        "additionalProperties": False,
    },
}

SERVICE_STATUS_SCHEMA = {
    "name": "service_status",
    "description": "Get the current status of one IT service (operational, degraded or outage), with when it "
    "started and a note. Use it when a user asks whether a service is working or down.",
    "parameters": {
        "type": "object",
        "properties": {
            "service": {
                "type": "string",
                "enum": SERVICES,
                "description": "The service, exactly as listed",
            },
        },
        "required": ["service"],
        "additionalProperties": False,
    },
}

# TODO (Activity 2): describe find_tickets to the model. Replace this placeholder.
# Rules (tests/test_tool_schemas.py checks each one):
# - "name": "find_tickets"
# - "description": at least 60 characters, saying what the tool does and when to use it
#   (questions about which tickets exist or how many there are)
# - "parameters": a JSON Schema object with exactly four optional properties, each with a "description":
#     status       a string, one of STATUSES
#     application  a string (you may also give the list of applications as an enum)
#     severity     a string, one of SEVERITIES
#     limit        an integer from 1 to 20
#   "required": [] and "additionalProperties": False
FIND_TICKETS_SCHEMA = {
    "name": "find_tickets",
    "description": "Search the help desk tickets by status, application or severity and return how many match "
    "plus the newest ones. Use it for questions about which tickets exist or how many there are, for "
    "example 'how many open Print Queue tickets are there?'. For one named ticket use get_ticket.",
    "parameters": {
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": STATUSES,
                "description": "Only tickets with this status",
            },
            "application": {
                "type": "string",
                "description": "Only tickets about this application, for example Print Queue or SecureLink VPN",
            },
            "severity": {
                "type": "string",
                "enum": SEVERITIES,
                "description": "Only tickets with this severity, P1 is the most urgent",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 20,
                "description": "How many tickets to list (default 10)",
            },
        },
        "required": [],
        "additionalProperties": False,
    },
}

FIND_ASSETS_SCHEMA = {
    "name": "find_assets",
    "description": "List the company's devices (laptops, desktops, monitors, docking stations, phones) from the "
    "device inventory, with asset tag, model and purchase date. Use it for questions about which devices a "
    "person or a department has, or when a device was bought. Give at least one filter. "
    "It does not know anything about tickets.",
    "parameters": {
        "type": "object",
        "properties": {
            "assigned_to": {
                "type": "string",
                "pattern": r"^[a-z]\.[a-z]+$",
                "description": "The username of the device's user, for example a.mensah",
            },
            "department": {
                "type": "string",
                "minLength": 2,
                "maxLength": 50,
                "description": "The department, for example Finance or HR",
            },
            "device_type": {
                "type": "string",
                "enum": DEVICE_TYPES,
                "description": "The kind of device",
            },
        },
        "required": [],
        "additionalProperties": False,
    },
}

GET_TICKET_SCHEMA = {
    "name": "get_ticket",
    "description": "Get one ticket by its id, including its notes. Use it when the user names a ticket such as INC-1017.",
    "parameters": {
        "type": "object",
        "properties": {
            "ticket_id": {
                "type": "string",
                "pattern": "^INC-[0-9]{4}$",
                "description": "For example INC-1017",
            },
        },
        "required": ["ticket_id"],
        "additionalProperties": False,
    },
}

UPDATE_TICKET_SCHEMA = {
    "name": "update_ticket",
    "description": "Change a ticket's status and add a note explaining why. This CHANGES DATA: the user is asked "
    "to approve it first. Only use it when the user clearly asks for a ticket to be changed.",
    "parameters": {
        "type": "object",
        "properties": {
            "ticket_id": {
                "type": "string",
                "pattern": "^INC-[0-9]{4}$",
                "description": "For example INC-1017",
            },
            "status": {
                "type": "string",
                "enum": STATUSES,
                "description": "The new status",
            },
            "note": {
                "type": "string",
                "minLength": 5,
                "maxLength": 300,
                "description": "Why the status changed",
            },
        },
        "required": ["ticket_id", "status", "note"],
        "additionalProperties": False,
    },
}

ASSIGN_TICKET_SCHEMA = {
    "name": "assign_ticket",
    "description": "Give an open ticket to a support team. This CHANGES DATA: the user is asked to approve it "
    "first. Only use it when the user clearly asks for a ticket to be given or assigned to a team. "
    "Closed tickets cannot be assigned.",
    "parameters": {
        "type": "object",
        "properties": {
            "ticket_id": {
                "type": "string",
                "pattern": "^INC-[0-9]{4}$",
                "description": "For example INC-1013",
            },
            "team": {
                "type": "string",
                "enum": TEAMS,
                "description": "The team that should own the ticket",
            },
        },
        "required": ["ticket_id", "team"],
        "additionalProperties": False,
    },
}

SEARCH_POLICIES_SCHEMA = {
    "name": "search_policies",
    "description": "Search the company's IT policy documents. Use it for any question about rules, limits, "
    "targets or how-to steps. Answer only from the sources it returns, and cite them as [1], [2].",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "minLength": 3,
                "maxLength": 500,
                "description": "The policy question, written as a full question",
            },
        },
        "required": ["question"],
        "additionalProperties": False,
    },
}


@dataclass
class Tool:
    fn: Callable
    schema: dict
    changes_data: bool = False


TOOLS = {
    "calculate": Tool(calculate, CALCULATE_SCHEMA),
    "service_status": Tool(service_status, SERVICE_STATUS_SCHEMA),
    "find_tickets": Tool(find_tickets, FIND_TICKETS_SCHEMA),
    "find_assets": Tool(find_assets, FIND_ASSETS_SCHEMA),
    "get_ticket": Tool(get_ticket, GET_TICKET_SCHEMA),
    "update_ticket": Tool(update_ticket, UPDATE_TICKET_SCHEMA, changes_data=True),
    "assign_ticket": Tool(assign_ticket, ASSIGN_TICKET_SCHEMA, changes_data=True),
    "search_policies": Tool(search_policies, SEARCH_POLICIES_SCHEMA),
}


def tool_list(tools=TOOLS) -> list:
    """The tools in the format the chat API expects."""
    return [{"type": "function", "function": t.schema} for t in tools.values()]


def log_action(entry: dict, path: str = ACTIONS_LOG) -> None:
    """Append one line to the audit log of actions that change data (approved or not)."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "time": datetime.now().astimezone().isoformat(timespec="seconds"),
                    **entry,
                }
            )
            + "\n"
        )
