"""Day 7 names for the Day 6 model call: MODEL and an OpenAI-style llm_client().

The client has the one method Day 7 uses, client.chat.completions.create(...), and keeps the
Day 6 safety rules: a timeout and max_tokens on every call, and the key is never printed.
"""
import json
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
    """Mimics client.chat.completions: one create() call that talks to OpenRouter."""

    def create(self, model, messages, temperature=0, max_tokens=MAX_TOKENS, stream=False):
        # The key comes from .env; it is read here and never printed or logged.
        key = os.getenv("OPENROUTER_API_KEY")
        if not key:
            raise LLMError("OPENROUTER_API_KEY is not set. Check .env.")
        if stream:
            return self._stream(key, model, messages, temperature, max_tokens)
        try:
            # timeout and max_tokens keep one slow or runaway call from hanging or costing too much.
            resp = requests.post(
                OPENROUTER_URL,
                headers={"Authorization": f"Bearer {key}"},
                json={"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
                timeout=LLM_TIMEOUT,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        except (requests.RequestException, KeyError, IndexError, ValueError) as err:
            # Network error, bad status or unexpected reply shape: one safe message, no key or URL leaked.
            raise LLMError(f"The model could not be reached ({type(err).__name__}).") from err
        # Wrap the text so callers can read reply.choices[0].message.content, as with the OpenAI client.
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def _stream(self, key, model, messages, temperature, max_tokens):
    """Yield chunks shaped like the openai library's (chunk.choices[0].delta.content), one per piece."""
    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "messages": messages, "temperature": temperature,
                  "max_tokens": max_tokens, "stream": True},
            timeout=LLM_TIMEOUT,
            stream=True,
        )
        resp.raise_for_status()
        for line in resp.iter_lines(decode_unicode=True):
            # Server-sent events: lines look like "data: {json}", and the last is "data: [DONE]".
            if not line or not line.startswith("data: "):
                continue
            data = line[len("data: "):]
            if data == "[DONE]":
                break
            for choice in json.loads(data).get("choices", []):
                text = (choice.get("delta") or {}).get("content")
                yield SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=text))])
    except (requests.RequestException, ValueError) as err:
        raise LLMError(f"The model could not be reached ({type(err).__name__}).") from err


_Completions._stream = _stream


def llm_client():
    """A client shaped like OpenAI's: client.chat.completions.create(...)."""
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


# Day 9: names that app/streaming.py expects.
from app.answer import build_messages  # noqa: E402
from app.config import DECLINE_SENTENCE as DECLINE  # noqa: E402,F401


def build_prompt(question: str, kept: list) -> str:
    """The system rules plus the numbered sources and the question, as one prompt string."""
    return "\n\n".join(m["content"] for m in build_messages(question, kept))
