"""Helpers for the Day 13 tests: a fresh copy of the help desk database, and a client that talks to
the MCP server in the same process (no subprocess, no Node, no model)."""

import asyncio
import json

import pytest
from mcp import Client

from app import mcp_server
from scripts import make_helpdesk_db, make_staff_table


@pytest.fixture
def db(tmp_path, monkeypatch):
    """Build data/helpdesk.db with the staff table in a temporary folder; send the query log there too."""
    path = str(tmp_path / "helpdesk.db")
    make_helpdesk_db.build(db=path)
    make_staff_table.build(db=path)
    monkeypatch.setattr(
        mcp_server, "QUERY_LOG", str(tmp_path / "logs" / "mcp_queries.jsonl")
    )
    return path


def read_log(db_path):
    """The query log entries written during the test."""
    try:
        with open(mcp_server.QUERY_LOG, encoding="utf-8") as f:
            return [json.loads(line) for line in f]
    except FileNotFoundError:
        return []


def with_client(server, work):
    """Connect a client to the server in-process, run await work(client), and return its result."""

    async def main():
        async with Client(server) as client:
            return await work(client)

    return asyncio.run(main())


def call_tool(server, name, args=None):
    return with_client(server, lambda c: c.call_tool(name, args or {}))
