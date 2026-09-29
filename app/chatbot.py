"""Day 3, Activity 4: a command-line chatbot with history, model switching and a usage log.

Your job: implement ask() so the tests in tests/test_chatbot.py pass. Everything else is done.
Check your work:  pytest -q tests/test_chatbot.py
Then run it:      python -m app.chatbot
Commands: /model <name>, /models, /reset, /exit
"""

import csv
import os
import time
from datetime import datetime, timezone
from typing import Any, NamedTuple

from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)

load_dotenv()

SYSTEM = "You are a helpful IT support assistant. Be concise."
USAGE_LOG = "data/usage.csv"


class Backend(NamedTuple):
    """One model backend. Unpacks as (client, model) like the Day 3 tests expect."""

    client: Any
    model: str
    in_price: float = 0.0  # $ per 1M input tokens
    out_price: float = 0.0  # $ per 1M output tokens


def build_backends(env=None):
    """Name -> Backend, built from environment variables (see .env.example).

    BACKENDS=hosted,strong,local lists the names; for each name NAME the variables
    NAME_BASE_URL, NAME_KEY_VAR, NAME_MODEL, NAME_IN_PRICE and NAME_OUT_PRICE apply.
    Adding a model is a configuration change: add a name and its variables.
    """
    env = os.environ if env is None else env
    out = {}
    for name in (n.strip() for n in env.get("BACKENDS", "").split(",")):
        if not name:
            continue
        p = name.upper()
        model = env.get(f"{p}_MODEL")
        if not model:
            raise RuntimeError(f"{p}_MODEL is not set; add it to .env")
        key = env.get(env.get(f"{p}_KEY_VAR", ""), "") or "none"
        out[name] = Backend(
            client=OpenAI(base_url=env.get(f"{p}_BASE_URL"), api_key=key),
            model=model,
            in_price=float(env.get(f"{p}_IN_PRICE", "0")),
            out_price=float(env.get(f"{p}_OUT_PRICE", "0")),
        )
    if not out:
        raise RuntimeError("BACKENDS is empty; see .env.example")
    return out


def prices_for(model, backends=None):
    """(input, output) $ per 1M tokens for a model ID, from the registry."""
    try:
        backends = backends or build_backends()
    except RuntimeError:
        backends = {}
    for b in backends.values():
        if b.model == model:
            return b.in_price, b.out_price
    return 0.0, 0.0


def describe_backends(backends):
    """Lines for /models: name, model ID and prices."""
    return [
        f"{name:8} {b.model}  in=${b.in_price:g}/1M  out=${b.out_price:g}/1M"
        for name, b in backends.items()
    ]


def log_usage(model, usage, seconds, path=USAGE_LOG):
    """Append one row per call: time, model, tokens, seconds and cost. Returns the cost."""
    in_price, out_price = prices_for(model)
    p = getattr(usage, "prompt_tokens", 0) or 0
    c = getattr(usage, "completion_tokens", 0) or 0
    cost = (p / 1e6) * in_price + (c / 1e6) * out_price
    new = not os.path.exists(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(
                [
                    "timestamp",
                    "model",
                    "prompt_tokens",
                    "completion_tokens",
                    "seconds",
                    "cost",
                ]
            )
        w.writerow(
            [
                datetime.now(timezone.utc).isoformat(),
                model,
                p,
                c,
                round(seconds, 3),
                round(cost, 6),
            ]
        )
    return cost


def ask(backends, name, history, attempts=3, sleep=time.sleep, log=log_usage):
    """Call backends[name] with the history and return the reply text.

    Rules (tests/test_chatbot.py checks each one):
    - on success, call log(model, response.usage, seconds) and return the reply text
    - AuthenticationError: do not retry; return a message telling the user to check their key
    - RateLimitError, APITimeoutError, APIConnectionError: retry up to `attempts` times,
      calling sleep(1), sleep(2), sleep(4)... between tries (double the wait each time)
    - if every attempt fails and name is not "local", fall back to the "local" backend
    - if nothing works, return "No model is reachable right now."
    """
    retryable = (RateLimitError, APITimeoutError, APIConnectionError)
    order = [name] + ([] if name == "local" else ["local"])
    for n in order:
        if n not in backends:
            continue
        client, model = backends[n][0], backends[n][1]
        for attempt in range(attempts):
            start = time.perf_counter()
            try:
                r = client.chat.completions.create(model=model, messages=history)
            except AuthenticationError:
                return f"Authentication failed for '{n}': check your API key in .env."
            except retryable:
                if attempt < attempts - 1:
                    sleep(2**attempt)
                continue
            log(model, r.usage, time.perf_counter() - start)
            return r.choices[0].message.content or ""
    return "No model is reachable right now."


def handle_command(text, backends, current, history):
    """Return (handled, current, history). Commands never reach the model."""
    if text == "/models":
        print("\n".join(describe_backends(backends)))
        return True, current, history
    if text == "/reset":
        return True, current, [{"role": "system", "content": SYSTEM}]
    if text.startswith("/model "):
        name = text.split(maxsplit=1)[1].strip()
        current = name if name in backends else current
        print("now using:", current)
        return True, current, history
    return False, current, history


def main():
    backends = build_backends()
    current = os.getenv("DEFAULT_BACKEND") or next(iter(backends))
    history = [{"role": "system", "content": SYSTEM}]
    while True:
        text = input(f"[{current}] you: ").strip()
        if text == "/exit":
            break
        handled, current, history = handle_command(text, backends, current, history)
        if handled or not text:
            continue
        history.append({"role": "user", "content": text})
        reply = ask(backends, current, history)
        history.append({"role": "assistant", "content": reply})
        print("bot:", reply)


if __name__ == "__main__":
    main()
