"""Tells you when Activity 2 is done: all five tests pass. The judge model is a fake."""

from app.judge import judge_answer
from tests.day08_fakes import FakeChatClient

ARGS = (
    "How often are laptops replaced?",
    "Every 4 years",
    "Every 3 years [1].",
    "[1] (equipment.pdf, page 1)\nLaptops are replaced every 4 years.",
)
VERDICT = (
    '{"correct": false, "grounded": false, "reason": "The source says 4 years, not 3."}'
)


def test_returns_the_judges_verdict():
    result = judge_answer(*ARGS, client=FakeChatClient(VERDICT))
    assert result == {
        "correct": False,
        "grounded": False,
        "reason": "The source says 4 years, not 3.",
    }


def test_calls_the_model_once_at_temperature_zero_with_the_given_model():
    fake = FakeChatClient(VERDICT)
    judge_answer(*ARGS, client=fake, model="judge-model")
    assert len(fake.calls) == 1
    assert fake.calls[0]["temperature"] == 0 and fake.calls[0]["model"] == "judge-model"


def test_the_prompt_contains_everything_the_judge_needs():
    fake = FakeChatClient(VERDICT)
    judge_answer(*ARGS, client=fake)
    prompt = fake.calls[0]["messages"][0]["content"]
    for part in (
        "How often are laptops replaced?",
        "Every 4 years",
        "Every 3 years [1].",
        "Laptops are replaced every 4 years.",
    ):
        assert part in prompt


def test_a_verdict_inside_json_fences_is_read():
    fake = FakeChatClient(
        '```json\n{"correct": true, "grounded": true, "reason": "ok"}\n```'
    )
    assert judge_answer(*ARGS, client=fake)["correct"] is True


def test_an_unreadable_reply_does_not_crash():
    result = judge_answer(*ARGS, client=FakeChatClient("The answer looks fine to me."))
    assert result == {
        "correct": None,
        "grounded": None,
        "reason": "unreadable judge reply",
    }
