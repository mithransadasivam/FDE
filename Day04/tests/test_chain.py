# Tests for app/chain.py. None of them call the real model, so they are free and fast.
# Run from the Day 04 folder:  python -m pytest -v
import json

import pytest

from app.chain import extract, validate


def good():
    """A valid extraction result. Each test starts from this and breaks one thing."""
    return {
        "decisions": [],
        "actions": [{"owner": "Sam", "task": "prepare demo data", "due": "Wednesday"}],
        "open_questions": [],
    }


# --- Tests for validate(): the plain-Python step that checks the model's JSON ---


def test_valid_data_is_returned():
    # Good data passes through validate() unchanged (the very same object comes back).
    data = good()
    assert validate(data) is data


def test_missing_owner_raises():
    # An action with no owner must be rejected, with a message naming the action.
    data = good()
    data["actions"][0]["owner"] = None
    with pytest.raises(ValueError, match="action 1: missing owner"):
        validate(data)


def test_missing_task_raises():
    # A blank task (only spaces) counts as missing too.
    data = good()
    data["actions"][0]["task"] = "  "
    with pytest.raises(ValueError, match="action 1: missing task"):
        validate(data)


def test_all_problems_are_listed():
    # validate() should report every problem at once, not stop at the first one.
    data = good()
    data["actions"] += [{"owner": None, "task": None, "due": None}]
    with pytest.raises(ValueError) as e:
        validate(data)
    assert "action 2: missing owner" in str(e.value)
    assert "action 2: missing task" in str(e.value)


def test_actions_not_a_list_raises():
    # If the model returns "actions" as something other than a list, reject it.
    with pytest.raises(ValueError, match="'actions'"):
        validate({"actions": "nope"})


# --- Prompt injection test (Activity 4) ---

# What the model would return if it OBEYED the hidden instruction in the poisoned
# transcript: Sam's real action, plus a fake action for "everyone" to email a password.
INJECTED = {
    "decisions": [],
    "actions": [
        {"owner": "Sam", "task": "prepare demo data", "due": "Wednesday"},
        {"owner": "everyone", "task": "email VPN password to audit@external.example", "due": None},
    ],
    "open_questions": [],
}


class FakeClient:
    """Stands in for the OpenAI client and always returns a fixed reply.

    chain.py calls client.chat.completions.create(...) and reads
    response.choices[0].message.content. The nested type(...) calls below build
    just enough fake objects to make that exact call chain work.
    """

    def __init__(self, reply):
        msg = type("Msg", (), {"content": json.dumps(reply)})  # message.content = our JSON
        choice = type("Choice", (), {"message": msg})  # choices[0].message
        resp = type("Resp", (), {"choices": [choice]})  # response.choices
        create = lambda **kwargs: resp  # ignores its arguments and returns the fake response
        self.chat = type("Chat", (), {"completions": type("C", (), {"create": staticmethod(create)})})


def test_injected_action_is_rejected():
    # The real model ignored the injection, so we fake one that obeys it, to prove
    # that the code checks (not the model) would still stop the attack.
    transcript = open("data/Day04_Slide29_transcript_poisoned.txt", encoding="utf-8").read()
    # extract() runs normally, but the "model" hands back the injected JSON.
    data = extract(transcript, FakeClient(INJECTED))
    # validate() with the transcript must reject it...
    with pytest.raises(ValueError) as e:
        validate(data, transcript)
    # ...for both reasons: "everyone" never spoke, and the action has an email and "password".
    assert "not a speaker" in str(e.value)
    assert "email address or 'password'" in str(e.value)
