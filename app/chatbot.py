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

from openai import (  # noqa: F401
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)

from app.clients import HOSTED_MODEL, LOCAL_MODEL, hosted_client, local_client

SYSTEM = "You are a helpful IT support assistant. Be concise."
USAGE_LOG = "data/usage.csv"


def build_backends():
    """Name -> (client, model ID)."""
    return {
        "hosted": (hosted_client(), HOSTED_MODEL),
        "local": (local_client(), LOCAL_MODEL),
    }


def log_usage(model, usage, seconds, path=USAGE_LOG):
    """Append one row per call: time, model, tokens, seconds and cost. Returns the cost."""
    in_price = float(os.getenv("INPUT_PRICE", "0"))
    out_price = float(os.getenv("OUTPUT_PRICE", "0"))
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
    """TODO: call backends[name] with the history and return the reply text.

    Rules (tests/test_chatbot.py checks each one):
    - on success, call log(model, response.usage, seconds) and return the reply text
    - AuthenticationError: do not retry; return a message telling the user to check their key
    - RateLimitError, APITimeoutError, APIConnectionError: retry up to `attempts` times,
      calling sleep(1), sleep(2), sleep(4)... between tries (double the wait each time)
    - if every attempt fails and name is not "local", fall back to the "local" backend
    - if nothing works, return "No model is reachable right now."
    """
    raise NotImplementedError("TODO")


def handle_command(text, backends, current, history):
    """Return (handled, current, history). Commands never reach the model."""
    if text == "/models":
        print(", ".join(backends))
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
    backends, current = build_backends(), "hosted"
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
