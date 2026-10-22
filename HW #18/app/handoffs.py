"""Day 14: structured handoffs. What one agent passes to the next, written down as a contract.

Each specialist must reply with one JSON object that matches its model below. The receiving side
checks it before anyone uses it, so a bad reply is caught at the handoff, not three agents later.

Done: the handoff models, HandoffError and ask_for().
Activity 1: fill in parse_handoff(). Check it with tests/test_handoffs.py.
"""

import json
from typing import Literal

from pydantic import BaseModel, Field, ValidationError


class HandoffError(ValueError):
    """A reply that cannot be used as a handoff. The message says what is wrong."""


class Fact(BaseModel):
    text: str = Field(min_length=5, description="One fact, in one sentence")
    source: str = Field(
        min_length=2,
        description="Where it came from: a tool, a policy or an article id",
    )


class ResearchNotes(BaseModel):
    """Researcher -> writer and reviewer."""

    topic: str
    facts: list[Fact] = Field(min_length=1, max_length=12)
    open_questions: list[str] = Field(default_factory=list)


class Notice(BaseModel):
    """Writer -> reviewer and the person who approves it."""

    title: str = Field(min_length=5, max_length=80)
    audience: str = Field(description='Who it is for, for example "All staff"')
    body: str = Field(min_length=20)
    actions: list[str] = Field(
        default_factory=list, description="What staff should do, one per line"
    )
    sources: list[str] = Field(default_factory=list)


class Review(BaseModel):
    """Reviewer -> supervisor."""

    verdict: Literal["approve", "revise"]
    issues: list[str] = Field(default_factory=list)


def schema_for(model: type[BaseModel]) -> str:
    """The JSON Schema of a handoff, for the prompt."""
    return json.dumps(model.model_json_schema(), indent=None)


def parse_handoff(text: str, model: type[BaseModel]) -> BaseModel:
    """Turn a model's reply into a checked handoff object, or explain why not.

    Rules (tests/test_handoffs.py checks each one):
    - take the text from the first "{" to the last "}" (this skips ```json fences and any words around it)
        no "{" ... "}" at all:  raise HandoffError("no JSON object found")
    - data = json.loads(that text)
        json.JSONDecodeError e:  raise HandoffError(f"not valid JSON: {e.msg}")
    - return model.model_validate(data)
        ValidationError e:  raise HandoffError(f"does not match {model.__name__}: " + "; ".join(problems))
        where each of the first three problems is "<field path joined with .>: <msg>",
        from e.errors(): for example "facts.0.source: Field required"
    """
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        raise HandoffError("no JSON object found")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        raise HandoffError(f"not valid JSON: {e.msg}")
    try:
        return model.model_validate(data)
    except ValidationError as e:
        problems = [
            ".".join(str(part) for part in err["loc"]) + ": " + err["msg"]
            for err in e.errors()[:3]
        ]
        raise HandoffError(f"does not match {model.__name__}: " + "; ".join(problems))


def ask_for(
    client,
    model_name: str,
    system: str,
    user: str,
    schema: type[BaseModel],
    retries: int = 1,
):
    """Ask a specialist for a handoff. If the reply does not parse, tell it what was wrong and ask again
    (once by default). Raises HandoffError if it still fails."""
    messages = [
        {
            "role": "system",
            "content": system
            + "\n\nReply with only one JSON object matching this schema:\n"
            + schema_for(schema),
        },
        {"role": "user", "content": user},
    ]
    for attempt in range(retries + 1):
        reply = client.chat.completions.create(
            model=model_name, temperature=0, messages=messages
        )
        text = reply.choices[0].message.content or ""
        try:
            return parse_handoff(text, schema)
        except HandoffError as e:
            if attempt == retries:
                raise
            messages += [
                {"role": "assistant", "content": text},
                {
                    "role": "user",
                    "content": f"That reply could not be used: {e}. Reply again with only the JSON object.",
                },
            ]
    raise HandoffError("no reply")  # not reached
