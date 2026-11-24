"""Ticket ENG-902: stop a run before it goes on too long, costs too much, or goes round in circles.
Run: python -m pytest -q tests/test_limits.py"""

from app.agent.limits import check_limits

LIMITS = {"max_steps": 25, "max_tokens": 150000, "max_seconds": 300, "max_repeats": 3}
SAVE = {"tool": "click", "args": {"name": "Save"}}


def step(tool="look", tokens=1000, **args):
    return {"tool": tool, "args": args, "tokens_in": tokens, "tokens_out": 0}


def test_a_normal_step_may_go_ahead():
    assert check_limits([step("get_exception", ticket_id="KX-1001")], {"tool": "get_customer", "args": {"customer_id": "CU-022578"}},
                        LIMITS, 1000, 1010) is None


def test_the_step_limit():
    steps = [step("type", field="Note", text=str(i)) for i in range(25)]
    assert check_limits(steps, SAVE, LIMITS, 1000, 1010) == "Step limit: 25 steps"
    assert check_limits(steps[:24], SAVE, LIMITS, 1000, 1010) is None


def test_the_token_budget_counts_tokens_in_and_out():
    steps = [step(tokens=60000), {"tool": "look", "args": {}, "tokens_in": 60000, "tokens_out": 30000}]
    assert check_limits(steps, SAVE, LIMITS, 1000, 1010) == "Token budget: 150,000 tokens used"


def test_the_time_limit():
    assert check_limits([step()], SAVE, LIMITS, 1000, 1300) == "Time limit: 300 s"
    assert check_limits([step()], SAVE, LIMITS, 1000, 1299) is None


def test_the_same_action_a_third_time_in_a_row_is_stopped():
    steps = [step("choose", field="Outcome", option="Refer to Financial Crime"), step("click", name="Save"), step("click", name="Save")]
    assert check_limits(steps, SAVE, LIMITS, 1000, 1010) == 'Repeating: click "Save" 3 times in a row'


def test_twice_is_allowed_and_a_different_action_in_between_resets_the_count():
    assert check_limits([step("click", name="Save")], SAVE, LIMITS, 1000, 1010) is None
    steps = [step("click", name="Save"), step("look"), step("click", name="Save")]
    assert check_limits(steps, SAVE, LIMITS, 1000, 1010) is None


def test_same_tool_with_different_arguments_is_not_a_repeat():
    steps = [step("type", field="Note", text="a"), step("type", field="Note", text="b")]
    assert check_limits(steps, {"tool": "type", "args": {"field": "Note", "text": "c"}}, LIMITS, 1000, 1010) is None


def test_the_order_of_the_checks():
    steps = [step("click", tokens=6000, name="Save") for _ in range(25)]
    assert check_limits(steps, SAVE, LIMITS, 1000, 2000) == "Step limit: 25 steps"
    assert check_limits(steps[:2], SAVE, {**LIMITS, "max_tokens": 10000}, 1000, 2000) == "Token budget: 10,000 tokens used"
