"""Day 17, Activity 4: restrict_tools() gives an agent only the tools its job needs."""

import pytest

from app.memory import NoteBook
from app.permissions import PERMISSIONS, all_tools, restrict_tools


@pytest.fixture
def tools():
    return all_tools(NoteBook())


def test_an_unknown_role_gets_an_error_not_every_tool(tools):
    with pytest.raises(KeyError):
        restrict_tools(tools, "intern_agent")


def test_the_research_agent_gets_exactly_its_list(tools):
    allowed = restrict_tools(tools, "research_agent")
    assert sorted(allowed) == sorted(PERMISSIONS["research_agent"]["allow"])
    assert "update_ticket" not in allowed and "run_sql" not in allowed


def test_the_tools_given_are_not_changed(tools):
    before = dict(tools)
    restrict_tools(tools, "research_agent")
    assert tools == before and "run_sql" in tools


def test_a_change_always_needs_approval(tools):
    assert tools["update_ticket"].changes_data is False  # the approval was switched off
    allowed = restrict_tools(tools, "service_desk_assistant")
    assert allowed["update_ticket"].changes_data is True
    assert tools["update_ticket"].changes_data is False
    assert allowed["get_ticket"] is tools["get_ticket"]


def test_a_listed_tool_that_does_not_exist_is_skipped():
    from app.tools import TOOLS

    allowed = restrict_tools(
        {"get_ticket": TOOLS["get_ticket"]}, "service_desk_assistant"
    )
    assert list(allowed) == ["get_ticket"]


def test_the_agent_attacks_fail_without_the_tools(red_team_env):
    from app.red_team import load_attacks, run_attack

    attacks = {a["id"]: a for a in load_attacks()}
    for attack_id in ["A03", "A04", "A05"]:
        assert run_attack(attacks[attack_id], profile="wide")["succeeded"] is True, (
            attack_id
        )
        assert run_attack(attacks[attack_id], profile="least")["succeeded"] is False, (
            attack_id
        )
