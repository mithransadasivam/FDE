"""Day 7 names for the Day 6 model call: MODEL and an OpenAI-style llm_client().

The client has the one method Day 7 uses, client.chat.completions.create(...), and keeps the
Day 6 safety rules: a timeout and max_tokens on every call, and the key is never printed.
"""
import os
from types import SimpleNamespace

import requests
from dotenv import load_dotenv

from app.config import LLM_TIMEOUT, ROOT
from app.llm import OPENROUTER_URL, LLMError

load_dotenv(ROOT / ".env")
MODEL = os.getenv("LLM_MODEL", "anthropic/claude-haiku-4.5")
MAX_TOKENS = 300


class _Completions:
    def create(self, model, messages, temperature=0, max_tokens=MAX_TOKENS):
        key = os.getenv("OPENROUTER_API_KEY")
        if not key:
            raise LLMError("OPENROUTER_API_KEY is not set. Check .env.")
        try:
            resp = requests.post(
                OPENROUTER_URL,
                headers={"Authorization": f"Bearer {key}"},
                json={"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
                timeout=LLM_TIMEOUT,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        except (requests.RequestException, KeyError, IndexError, ValueError) as err:
            raise LLMError(f"The model could not be reached ({type(err).__name__}).") from err
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def llm_client():
    return SimpleNamespace(chat=SimpleNamespace(completions=_Completions()))
