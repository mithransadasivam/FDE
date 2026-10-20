"""Day 12: the research tools work, and give the agent no way to change data. Done: these pass from the start."""

import json

import pytest

from app.memory import NoteBook
from app.research_tools import agent_tools, read_article, web_search
from app.tool_loop import run_tool


def test_web_search_finds_the_vendor_article_for_an_error_code():
    ids = [r["id"] for r in web_search("VPN-809 certificate expired")["results"]]
    assert ids[0] == "KB-1101" and len(ids) <= 3


def test_read_article_returns_the_date_and_rejects_unknown_ids():
    assert read_article("KB-0412")["published"] == "2019-06-11"
    with pytest.raises(ValueError):
        read_article("KB-9999")


def test_the_agent_cannot_change_tickets():
    tools = agent_tools(NoteBook())
    assert "update_ticket" not in tools and not any(
        t.changes_data for t in tools.values()
    )


def test_notes_are_saved_once_and_checked_like_any_tool_call():
    nb = NoteBook()
    tools = agent_tools(nb)
    args = json.dumps(
        {"text": "VPN-809 means the certificate expired", "source": "KB-1101"}
    )
    assert json.loads(run_tool("save_note", args, tools))["saved"] is True
    assert json.loads(run_tool("save_note", args, tools))["saved"] is False
    assert "invalid arguments" in run_tool("save_note", '{"text": "hi"}', tools)


def test_a_note_needs_text_and_a_source():
    with pytest.raises(ValueError):
        NoteBook().add("  ", "KB-1101")
