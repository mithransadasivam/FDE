"""The chatbot as a service (Day 15), made faster and cheaper (Day 16). The API calls these
functions; they check the cache, find the sources, choose a model, open its stream (with retries
and a fallback), count the tokens and the cost, and record each step as a span.

Day 16 replaced this file: it contains the finished Day 15 code plus the Day 16 parts.
Settings (in .env or docker-compose.yml):
    CACHE=1          answer repeated questions from the response cache (app/cache.py)
    ROUTING=1        send simple questions to SMALL_MODEL (app/router.py)
    SMALL_MODEL      default ollama/llama3.2:3b: a quantised open model served by Ollama
    MAX_TOKENS       the longest answer, in tokens (default 400)

With CHAT_FAKE=1 the service uses Day 9's fake chatbot: no Ollama, no API key, no cost.
Nothing in this file is a TODO.
"""

import hashlib
import os
from pathlib import Path
from urllib.request import urlopen

from dotenv import load_dotenv

from app.cache import ResponseCache, cache_key
from app.perf import estimate_tokens, request_cost
from app.rag import DECLINE, MODEL, PROMPT, build_prompt
from app.reliability import TIMEOUT, SimulatedOutage, call_with_fallback
from app.router import choose_route
from app.tracing import trace_step

load_dotenv()
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "openai/gpt-4.1-mini")
SMALL_MODEL = os.getenv("SMALL_MODEL", "ollama/llama3.2:3b")
LOCAL_TIMEOUT = float(
    os.getenv("LOCAL_TIMEOUT", "120")
)  # a laptop CPU is slower than a provider
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "400"))
# A short fingerprint of the prompt template: change the prompt and the version changes with it
PROMPT_VERSION = "rag-" + hashlib.sha256(PROMPT.encode()).hexdigest()[:8]


def fake_mode() -> bool:
    return os.getenv("CHAT_FAKE") == "1"


def cache_on() -> bool:
    return os.getenv("CACHE") == "1"


def routing_on() -> bool:
    return os.getenv("ROUTING") == "1"


def models(route: str = "large") -> list[str]:
    """The models to try, in order. Large: the primary, then the fallback. Small: the small model,
    then the primary (a small model that fails falls back to the large one)."""
    if fake_mode():
        return (
            ["fake-small", "fake-primary"]
            if route == "small"
            else ["fake-primary", "fake-fallback"]
        )
    return [SMALL_MODEL, MODEL] if route == "small" else [MODEL, FALLBACK_MODEL]


def check_outage(model: str) -> None:
    """SIMULATE_OUTAGE=primary makes the primary model fail, as if its provider were down;
    =small makes the small model fail; =all makes every model fail."""
    outage = os.getenv("SIMULATE_OUTAGE")
    if (
        outage == "all"
        or (outage == "primary" and model == models("large")[0])
        or (outage == "small" and model == models("small")[0])
    ):
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


def local_client():
    """The same OpenAI library, pointed at Ollama on this machine: Ollama speaks the same API."""
    from openai import OpenAI

    from app.embeddings import OLLAMA_URL

    return OpenAI(
        base_url=OLLAMA_URL, api_key="ollama", timeout=LOCAL_TIMEOUT, max_retries=0
    )


def client_for(model: str):
    """(client, the model name that client expects). "ollama/llama3.2:3b" -> Ollama, "llama3.2:3b"."""
    if model.startswith("ollama/"):
        return local_client(), model.removeprefix("ollama/")
    return model_client(), model


def find(question: str) -> dict:
    if fake_mode():
        from app.chat_fake import find_sources
    else:
        from app.streaming import find_sources
    return find_sources(question)


def scores(kept: list) -> list[dict]:
    """The kept chunks' scores, for the router (the fake chatbot's chunks have none: 0.8 each)."""
    return [{"score": c["score"] if isinstance(c, dict) else 0.8} for c in kept]


def open_stream(question: str, kept: list, model: str, usage: dict):
    """Start the model's reply. Errors when connecting happen here, so call_with_fallback sees them.
    Returns an iterator of text pieces; usage gets prompt_tokens and completion_tokens at the end
    (estimated from the text, with usage["estimated"] = True, if the server reports none)."""
    check_outage(model)
    if fake_mode():
        from app.chat_fake import stream_answer

        def fake_pieces():
            text = ""
            for piece in stream_answer(question, kept):
                text += piece
                yield piece
            usage.update(prompt_tokens=600, completion_tokens=estimate_tokens(text))

        return fake_pieces()
    prompt = build_prompt(question, kept)
    client, name = client_for(model)
    stream = client.chat.completions.create(
        model=name,
        temperature=0,
        max_tokens=MAX_TOKENS,
        stream=True,
        stream_options={"include_usage": True},
        messages=[{"role": "user", "content": prompt}],
    )

    def pieces():
        text = ""
        for chunk in stream:
            u = getattr(chunk, "usage", None)
            if u:
                usage.update(
                    prompt_tokens=getattr(u, "prompt_tokens", None) or 0,
                    completion_tokens=getattr(u, "completion_tokens", None)
                    or getattr(u, "total_tokens", 0),
                )
            if chunk.choices and chunk.choices[0].delta.content:
                text += chunk.choices[0].delta.content
                yield chunk.choices[0].delta.content
        if "prompt_tokens" not in usage:
            usage.update(
                prompt_tokens=estimate_tokens(prompt),
                completion_tokens=estimate_tokens(text),
                estimated=True,
            )

    return pieces()


def prepare(question: str) -> dict:
    """Find the sources, choose the route, and open the reply. Returns {"sources", "model",
    "fallback", "attempts", "route", "route_reason", "pieces", "usage"}; pieces yields the text."""
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
            "route": None,
            "route_reason": "nothing relevant found",
            "pieces": iter([DECLINE]),
            "usage": usage,
        }
    if routing_on():
        route = choose_route(
            question, scores(found["kept"]), small_available=bool(SMALL_MODEL)
        )
    else:
        route = {"route": "large", "reason": "routing is off"}
    with trace_step(
        "open_model_stream",
        prompt_version=PROMPT_VERSION,
        route=route["route"],
        route_reason=route["reason"],
    ) as span:
        opened = call_with_fallback(
            lambda m: open_stream(found["query"], found["kept"], m, usage),
            models(route["route"]),
        )
        span.set_attribute("chatbot.model", opened["model"])
        span.set_attribute("chatbot.fallback", opened["fallback"])
        span.set_attribute("chatbot.attempts", opened["attempts"])
    return {
        "sources": found["sources"],
        "model": opened["model"],
        "fallback": opened["fallback"],
        "attempts": opened["attempts"],
        "route": route["route"],
        "route_reason": route["reason"],
        "pieces": opened["result"],
        "usage": usage,
    }


def finish(p: dict, text: str) -> dict:
    """The answer, with its tokens and cost, once the whole text has arrived."""
    pt, ct = p["usage"].get("prompt_tokens"), p["usage"].get("completion_tokens")
    return {
        "answer": text,
        "sources": p["sources"],
        "declined": text == DECLINE,
        "model": p["model"],
        "fallback": p["fallback"],
        "route": p["route"],
        "route_reason": p["route_reason"],
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "tokens": (pt or 0) + (ct or 0) if p["model"] else None,
        "cost_usd": request_cost(p["model"], pt, ct),
        "cached": False,
    }


# ------------------------------------------------------------------ the response cache
_cache = None


def get_cache() -> ResponseCache:
    global _cache
    if _cache is None:
        _cache = ResponseCache()
    return _cache


def key_for(question: str) -> str:
    """Everything that would change the answer is part of the key."""
    setup = ",".join(models("large") + models("small")) + f"|routing={routing_on()}"
    return cache_key(question, PROMPT_VERSION, setup)


def from_cache(question: str) -> dict | None:
    """A saved answer for this question, costing nothing: or None (also when CACHE is off)."""
    if not cache_on():
        return None
    with trace_step("cache_lookup") as span:
        hit = get_cache().get(key_for(question))
        span.set_attribute("chatbot.cache", "hit" if hit else "miss")
    if hit:
        hit.update(prompt_tokens=0, completion_tokens=0, tokens=0, cost_usd=0.0)
    return hit


def save_to_cache(question: str, result: dict) -> None:
    if cache_on():
        get_cache().put(
            key_for(question), {k: v for k, v in result.items() if k != "cached"}
        )


def answer(question: str) -> dict:
    """The whole answer at once, for POST /ask. Raises ModelUnavailable if every model failed."""
    hit = from_cache(question)
    if hit:
        return hit
    with trace_step("ask", question_chars=len(question), fake=fake_mode()) as span:
        p = prepare(question)
        with trace_step("generate", model=p["model"]):
            text = "".join(p["pieces"]).strip()
        result = finish(p, text)
        span.set_attribute("chatbot.declined", result["declined"])
        span.set_attribute("chatbot.cost_usd", result["cost_usd"])
    save_to_cache(question, result)
    return result


# ------------------------------------------------------------------ readiness (Day 15)
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


def check_small_model() -> tuple[bool, str]:
    """With ROUTING=1 and an ollama/ small model, Ollama must have pulled it."""
    if not SMALL_MODEL.startswith("ollama/"):
        return True, f"{SMALL_MODEL} is a hosted model"
    name = SMALL_MODEL.removeprefix("ollama/")
    found = [m.id for m in local_client().models.list().data]
    ok = name in found
    return (
        ok,
        f"{name} is in Ollama"
        if ok
        else f"{name} is not in Ollama: run ollama pull {name}",
    )


def default_checks() -> list:
    if fake_mode():
        return [
            ("mode", lambda: (True, "CHAT_FAKE=1: the fake chatbot needs nothing else"))
        ]
    checks = [
        ("api_key", check_api_key),
        ("index", check_index),
        ("ollama", check_ollama),
    ]
    if routing_on():
        checks.append(("small_model", check_small_model))
    return checks


def readiness(checks=None) -> dict:
    """Is the service ready to answer questions? Used by GET /ready (Day 15, Activity 2)."""
    results = {}
    for name, check in default_checks() if checks is None else checks:
        try:
            ok, detail = check()
        except Exception as error:  # noqa: BLE001  (any failure means "not ready")
            ok, detail = False, f"{type(error).__name__}: {error}"
        results[name] = {"ok": bool(ok), "detail": detail}
    return {"ready": all(r["ok"] for r in results.values()), "checks": results}
