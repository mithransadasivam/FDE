"""Models. One tiny interface (`chat`) with three implementations:

  OpenRouterLLM  the hosted model named by LLM_MODEL in .env (the only one that touches the network)
  ScriptedLLM    a fake that returns replies you list in advance (unit tests)
  OfflineLLM     lives in offline_llm.py: a rule-based stand-in that behaves like a careful agent (demos, CI)

Every response carries its token counts and seconds, so cost can be compared between the single agent and the team.
No test may use OpenRouterLLM: tests/conftest.py blocks the network and removes the key.
"""
import json
import os
import threading
import time
from dataclasses import dataclass, field

import requests
from dotenv import load_dotenv

from vendor_desk import config

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class LLMError(RuntimeError):
    """The model is not configured, unreachable or returned something unusable."""


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    content: str = ""
    tool_calls: list = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0


@dataclass
class Usage:
    """Running totals for one run (model calls, tokens, seconds)."""
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0
    tool_calls: int = 0

    def add_response(self, r: LLMResponse):
        self.calls += 1
        self.prompt_tokens += r.prompt_tokens
        self.completion_tokens += r.completion_tokens
        self.seconds += r.seconds

    def merge(self, other: "Usage"):
        self.calls += other.calls
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.seconds += other.seconds
        self.tool_calls += other.tool_calls

    @property
    def tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def cost_usd(self) -> float:
        try:
            pin, pout = float(os.getenv("INPUT_PRICE", "0")), float(os.getenv("OUTPUT_PRICE", "0"))
        except ValueError:
            return 0.0
        return (self.prompt_tokens * pin + self.completion_tokens * pout) / 1_000_000

    def as_dict(self) -> dict:
        return {"model_calls": self.calls, "tool_calls": self.tool_calls, "tokens": self.tokens,
                "prompt_tokens": self.prompt_tokens, "completion_tokens": self.completion_tokens,
                "seconds": round(self.seconds, 2), "cost_usd": round(self.cost_usd(), 5)}


def assistant_message(r: LLMResponse) -> dict:
    """The assistant turn in OpenAI chat format, so it can be appended to the conversation."""
    msg = {"role": "assistant", "content": r.content or ""}
    if r.tool_calls:
        msg["tool_calls"] = [{"id": c.id, "type": "function",
                              "function": {"name": c.name, "arguments": json.dumps(c.arguments)}}
                             for c in r.tool_calls]
    return msg


class OpenRouterLLM:
    """The hosted model. Calls are spaced out and retried on 429/5xx so a 20-calls-a-minute account still works."""
    _lock = threading.Lock()
    _last_call = 0.0

    def __init__(self, model: str | None = None):
        load_dotenv(config.ROOT / ".env")
        if os.getenv("ENV_FILE"):          # optional: a .env kept outside the project (never printed or committed)
            load_dotenv(os.environ["ENV_FILE"])
        self.key = os.getenv("OPENROUTER_API_KEY")
        self.model = model or os.getenv("LLM_MODEL")
        if not self.key or not self.model:
            raise LLMError("The model is not configured. Put OPENROUTER_API_KEY and LLM_MODEL in .env (see .env.example).")
        self.min_interval = float(os.getenv("LLM_MIN_INTERVAL", "3.1"))

    def _throttle(self):
        with OpenRouterLLM._lock:
            wait = OpenRouterLLM._last_call + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            OpenRouterLLM._last_call = time.monotonic()

    def chat(self, messages, tools=None, max_tokens=None, role=None) -> LLMResponse:
        payload = {"model": self.model, "messages": messages, "temperature": 0,
                   "max_tokens": max_tokens or config.MAX_TOKENS}
        if tools:
            payload["tools"] = tools
        last_err = "unknown"
        for attempt in range(5):
            self._throttle()
            started = time.monotonic()
            try:
                resp = requests.post(OPENROUTER_URL, headers={"Authorization": f"Bearer {self.key}"},
                                     json=payload, timeout=config.LLM_TIMEOUT)
                if resp.status_code in (429, 500, 502, 503, 504):
                    last_err = f"HTTP {resp.status_code}"
                    time.sleep(min(8 * (attempt + 1), 40))
                    continue
                resp.raise_for_status()
                data = resp.json()
                msg = data["choices"][0]["message"]
                calls = []
                for c in msg.get("tool_calls") or []:
                    raw = c["function"].get("arguments") or "{}"
                    try:
                        args = json.loads(raw)
                    except json.JSONDecodeError:
                        args = {"_unparsed": raw[:200]}
                    calls.append(ToolCall(c.get("id") or f"call_{attempt}_{len(calls)}", c["function"]["name"], args))
                usage = data.get("usage") or {}
                return LLMResponse(msg.get("content") or "", calls, usage.get("prompt_tokens", 0),
                                   usage.get("completion_tokens", 0), time.monotonic() - started)
            except (requests.RequestException, KeyError, IndexError, ValueError, TypeError) as err:
                last_err = type(err).__name__  # never the request itself: it holds the key
                time.sleep(2 * (attempt + 1))
        raise LLMError(f"The model could not be reached ({last_err}).")


class ScriptedLLM:
    """A fake model for tests: returns the listed replies in order. Items may be an LLMResponse or a function
    (messages, tools) -> LLMResponse. Records every call so a test can inspect what the agent sent."""

    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def chat(self, messages, tools=None, max_tokens=None, role=None) -> LLMResponse:
        self.calls.append({"messages": json.loads(json.dumps(messages)), "tools": tools, "role": role})
        if not self.replies:
            raise AssertionError("ScriptedLLM ran out of replies: the agent made more model calls than the test expected")
        r = self.replies.pop(0)
        r = r(messages, tools) if callable(r) else r
        if not r.prompt_tokens:
            r = LLMResponse(r.content, r.tool_calls, 100, 20, 0.0)
        return r


def says(text: str) -> LLMResponse:
    return LLMResponse(content=text)


def calls(*specs, thought: str = "") -> LLMResponse:
    """calls(("read_request", {"request_id": "REQ-001"}), ...) -> a reply that asks for those tool calls."""
    return LLMResponse(content=thought, tool_calls=[ToolCall(f"call_{i}_{n}", n, a) for i, (n, a) in enumerate(specs)])


def make_llm(mode: str | None = None):
    """'live' = OpenRouter; 'offline' = the rule-based stand-in. Default comes from LLM_MODE, else live if configured."""
    mode = (mode or os.getenv("LLM_MODE") or "").lower()
    if mode == "offline":
        from vendor_desk.offline_llm import OfflineLLM
        return OfflineLLM()
    return OpenRouterLLM()
