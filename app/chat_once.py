"""Day 3, Activity 2: one streamed call that prints tokens and cost.

Your job: fill in the two TODO functions. The streaming code is done.
Check your work:  pytest -q tests/test_chat_once.py
Then run it:      python -m app.chat_once
"""

import os

from app.clients import HOSTED_MODEL, hosted_client

IN_PRICE = float(os.getenv("INPUT_PRICE", "0"))  # $ per 1M input tokens
OUT_PRICE = float(os.getenv("OUTPUT_PRICE", "0"))  # $ per 1M output tokens

SYSTEM = "You are a concise support assistant. Answer in at most 3 sentences."
QUESTION = "Our VPN certificate expired. What do I check first?"


def build_messages(system: str, question: str) -> list:
    """TODO 1: return the messages list: the system message first, then the user's question."""
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ]


def call_cost(
    prompt_tokens: int, completion_tokens: int, in_price: float, out_price: float
) -> float:
    """TODO 2: the cost of one call in dollars. Prices are per million tokens."""
    return (prompt_tokens / 1e6) * in_price + (completion_tokens / 1e6) * out_price


def main() -> None:
    messages = build_messages(SYSTEM, QUESTION)
    client = hosted_client()
    stream = client.chat.completions.create(
        model=HOSTED_MODEL,
        messages=messages,
        temperature=0.2,
        stream=True,
        stream_options={"include_usage": True},
    )
    usage = None
    for chunk in stream:
        if getattr(chunk, "usage", None):
            usage = chunk.usage
        if chunk.choices and chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)

    # Some providers do not report usage on a stream: measure it with one tiny call
    if usage is None:
        usage = client.chat.completions.create(
            model=HOSTED_MODEL, messages=messages, max_tokens=1
        ).usage

    cost = call_cost(usage.prompt_tokens, usage.completion_tokens, IN_PRICE, OUT_PRICE)
    print(
        f"\n\ntokens in={usage.prompt_tokens} out={usage.completion_tokens}  cost=$ {cost:.5f}"
    )


if __name__ == "__main__":
    main()
