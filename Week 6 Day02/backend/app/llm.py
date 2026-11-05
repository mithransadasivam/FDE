"""The model client, and ask_json(): ask for JSON, check it against a Pydantic model, retry once.

Same pattern as Phase 1: the OpenAI SDK pointed at OpenRouter, with OPENROUTER_API_KEY in .env.
Day 5 moves the model calls to Amazon Bedrock; only this file changes.

Set FDE_FAKE_LLM=1 to use scripted replies from backend/tests/fixtures instead of a real model
(the end-to-end tests do this, so they never need a key or the network).
"""

import json
import os
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

MODEL = os.getenv("FDE_MODEL", "anthropic/claude-sonnet-4.5")
FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


class LLMError(RuntimeError):
    """The model did not return valid JSON for the schema, even after one retry."""


class FakeLLM:
    """Scripted replies for FDE_FAKE_LLM=1: reply_for('findings') returns tests/fixtures/findings.json."""

    is_fake = True

    def reply_for(self, task: str) -> str:
        return (FIXTURES / f"{task}.json").read_text(encoding="utf-8")


def llm_client():
    if os.getenv("FDE_FAKE_LLM") == "1":
        return FakeLLM()
    from openai import OpenAI

    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise LLMError("OPENROUTER_API_KEY is missing: add it to .env in the repository root")
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)


def _json_text(text: str) -> str:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        raise ValueError("no JSON object found")
    return text[start : end + 1]


def ask_json(client, system: str, user: str, schema: type[BaseModel], task: str) -> BaseModel:
    """Ask the model for one JSON object that matches `schema`. If the reply is not valid,
    send the error back once and ask again. `task` names the fixture used in fake mode."""
    if getattr(client, "is_fake", False):
        return schema.model_validate_json(client.reply_for(task))

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    last_error = ""
    for attempt in range(2):
        reply = client.chat.completions.create(model=MODEL, messages=messages, temperature=0)
        text = reply.choices[0].message.content or ""
        try:
            return schema.model_validate(json.loads(_json_text(text)))
        except (ValueError, ValidationError) as e:
            last_error = str(e)[:600]
            messages += [
                {"role": "assistant", "content": text},
                {"role": "user", "content": f"That reply was not valid: {last_error}. Reply with the corrected JSON object only."},
            ]
    raise LLMError(f"{task}: no valid JSON after a retry ({last_error})")


def says(text: str):
    """A reply object shaped like the OpenAI SDK's, for tests."""
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text))])
