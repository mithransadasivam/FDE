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


# Day 8: names that scripts/eval_answers.py expects, built on this project's answer().
from app.answer import answer as _answer  # noqa: E402
from app.config import MIN_SCORE  # noqa: E402,F401


def format_sources(chunks: list[dict]) -> str:
    """The numbered sources the way the prompt shows them: [1] (file, page N) then the text."""
    return "\n\n".join(
        f"[{n}] ({c['source']}, page {c['page']})\n{c['text']}" for n, c in enumerate(chunks, 1)
    )


def answer(question: str, retrieve=None, **kwargs) -> dict:
    """Like app.answer.answer, but `sources` lists every chunk the prompt used (in citation
    order, so [n] maps to sources[n-1]) and `retrieve` takes only the question."""
    chunks = retrieve(question) if retrieve else None
    kwargs.setdefault("min_score", MIN_SCORE)
    result = _answer(question, retriever=(lambda q, k: chunks) if retrieve else kwargs.pop("retriever"), **kwargs)
    used = [c for c in (chunks or []) if c["score"] >= kwargs["min_score"]]
    result["sources"] = [] if result["declined"] else [f"{c['source']}, page {c['page']}" for c in used]
    return result
