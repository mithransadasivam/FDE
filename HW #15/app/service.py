"""Day 15: the chatbot as a service. The API calls these functions; they find the sources, open the
model's stream (with retries and a fallback model), and record each step as a span.

With CHAT_FAKE=1 the service uses Day 9's fake chatbot: no Ollama, no API key, no cost. That is how
the tests, the first container run and the CI pipeline work.

Done: prepare(), answer(), the model calls and the readiness checks.
Also done: readiness() (Activity 2). Check it with tests/test_readiness.py.
"""

import hashlib
import os
from pathlib import Path
from urllib.request import urlopen

from dotenv import load_dotenv

from app.rag import DECLINE, MODEL, PROMPT, build_prompt
from app.reliability import TIMEOUT, SimulatedOutage, call_with_fallback
from app.tracing import trace_step

load_dotenv()
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "openai/gpt-4.1-mini")
# A short fingerprint of the prompt template: change the prompt and the version changes with it
PROMPT_VERSION = "rag-" + hashlib.sha256(PROMPT.encode()).hexdigest()[:8]


def fake_mode() -> bool:
    return os.getenv("CHAT_FAKE") == "1"


def models() -> list[str]:
    """The primary model first, then the fallback."""
    if fake_mode():
        return ["fake-primary", "fake-fallback"]
    return [MODEL, FALLBACK_MODEL]


def check_outage(model: str) -> None:
    """SIMULATE_OUTAGE=primary makes the first model fail, as if its provider were down;
    SIMULATE_OUTAGE=all makes every model fail."""
    outage = os.getenv("SIMULATE_OUTAGE")
    if outage == "all" or (outage == "primary" and model == models()[0]):
        raise SimulatedOutage(f"simulated outage: {model} is not answering")


def model_client():
    """One OpenAI client for OpenRouter. max_retries=0: our own retry rules are the only ones."""
    from openai import OpenAI

    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=key,
        timeout=TIMEOUT,
        max_retries=0,
    )


def find(question: str) -> dict:
    if fake_mode():
        from app.chat_fake import find_sources
    else:
        from app.streaming import find_sources
    return find_sources(question)


def open_stream(question: str, kept: list, model: str, usage: dict):
    """Start the model's reply. Errors when connecting happen here, so call_with_fallback sees them.
    Returns an iterator of text pieces; usage["tokens"] is filled in when the reply ends."""
    check_outage(model)
    if fake_mode():
        from app.chat_fake import stream_answer

        def fake_pieces():
            for piece in stream_answer(question, kept):
                usage["tokens"] = usage.get("tokens", 0) + 1
                yield piece

        return fake_pieces()
    stream = model_client().chat.completions.create(
        model=model,
        temperature=0,
        stream=True,
        stream_options={"include_usage": True},
        messages=[{"role": "user", "content": build_prompt(question, kept)}],
    )

    def pieces():
        for chunk in stream:
            if getattr(chunk, "usage", None):
                usage["tokens"] = chunk.usage.total_tokens
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    return pieces()


def prepare(question: str) -> dict:
    """Find the sources and open the reply. Returns {"sources", "model", "fallback", "attempts",
    "pieces", "usage"}; pieces yields the answer text. Each step is a span in the trace."""
    usage = {}
    with trace_step("retrieve", question_chars=len(question)) as span:
        found = find(question)
        span.set_attribute("chatbot.chunks_kept", len(found["kept"]))
        span.set_attribute("chatbot.sources", "; ".join(found["sources"]))
    if not found["kept"]:
        return {
            "sources": [],
            "model": None,
            "fallback": False,
            "attempts": 0,
            "pieces": iter([DECLINE]),
            "usage": usage,
        }
    with trace_step("open_model_stream", prompt_version=PROMPT_VERSION) as span:
        opened = call_with_fallback(
            lambda m: open_stream(found["query"], found["kept"], m, usage), models()
        )
        span.set_attribute("chatbot.model", opened["model"])
        span.set_attribute("chatbot.fallback", opened["fallback"])
        span.set_attribute("chatbot.attempts", opened["attempts"])
    return {
        "sources": found["sources"],
        "model": opened["model"],
        "fallback": opened["fallback"],
        "attempts": opened["attempts"],
        "pieces": opened["result"],
        "usage": usage,
    }


def answer(question: str) -> dict:
    """The whole answer at once, for POST /ask. Raises ModelUnavailable if every model failed."""
    with trace_step("ask", question_chars=len(question), fake=fake_mode()) as span:
        p = prepare(question)
        with trace_step("generate", model=p["model"]):
            text = "".join(p["pieces"]).strip()
        span.set_attribute("chatbot.declined", text == DECLINE)
    return {
        "answer": text,
        "sources": p["sources"],
        "declined": text == DECLINE,
        "model": p["model"],
        "fallback": p["fallback"],
        "tokens": p["usage"].get("tokens"),
    }


# ------------------------------------------------------------------ readiness
def check_api_key() -> tuple[bool, str]:
    ok = bool(os.getenv("OPENROUTER_API_KEY"))
    return ok, "OPENROUTER_API_KEY is set" if ok else "OPENROUTER_API_KEY is missing"


def check_index() -> tuple[bool, str]:
    from app.indexing import CHROMA_PATH, get_collection

    if not Path(CHROMA_PATH).exists():
        return (
            False,
            f"no index at {CHROMA_PATH}: run python -m scripts.build_index_vision",
        )
    n = get_collection().count()
    return n > 0, f"{n} chunks in the index"


def check_ollama() -> tuple[bool, str]:
    from app.embeddings import OLLAMA_URL

    with urlopen(OLLAMA_URL.rstrip("/") + "/models", timeout=2) as r:
        return r.status == 200, f"Ollama answered at {OLLAMA_URL}"


def default_checks() -> list:
    if fake_mode():
        return [
            ("mode", lambda: (True, "CHAT_FAKE=1: the fake chatbot needs nothing else"))
        ]
    return [
        ("api_key", check_api_key),
        ("index", check_index),
        ("ollama", check_ollama),
    ]


def readiness(checks=None) -> dict:
    """Is the service ready to answer questions? Used by GET /ready.

    Rules (tests/test_readiness.py checks each one):
    - checks defaults to default_checks(): a list of (name, function) pairs; each function
      returns (ok, detail), for example (False, "OPENROUTER_API_KEY is missing")
    - run every check, even after one fails, so the reply lists every problem at once
    - a check that raises an error counts as failed, with detail f"{type(error).__name__}: {error}"
    - return {"ready": True only if every check passed,
              "checks": {name: {"ok": ok, "detail": detail}, ...}}
    """
    results = {}
    for name, check in checks if checks is not None else default_checks():
        try:
            ok, detail = check()
        except Exception as error:
            ok, detail = False, f"{type(error).__name__}: {error}"
        results[name] = {"ok": ok, "detail": detail}
    return {"ready": all(r["ok"] for r in results.values()), "checks": results}
