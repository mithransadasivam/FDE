"""The model client, and ask_json(): ask for JSON, check it against a Pydantic model, retry once.

Three ways to run, chosen in .env:

    FDE_FAKE_LLM=1               scripted replies from backend/tests/fixtures (tests, and the class without a key)
    FDE_LLM_PROVIDER=openrouter  the OpenAI SDK pointed at OpenRouter, as on Days 1-4 (OPENROUTER_API_KEY)
    FDE_LLM_PROVIDER=bedrock     Amazon Bedrock's Converse API in your AWS account (Day 5, ticket ENG-501)

Day 6: ask_json(..., image=<JPEG bytes>) also sends a picture of the page (the vision method). Every provider
takes it; set FDE_MODEL to a model that reads images (the class uses anthropic/claude-haiku-5.5).
A provider that says "too many requests" raises RateLimited, so the batch runner can wait and try again.

Bedrock uses your AWS credentials (aws configure, or the Lambda's IAM role in the pilot): there is no API key.
A guardrail is applied when FDE_GUARDRAIL_ID and FDE_GUARDRAIL_VERSION are set. In scripted mode,
FDE_GUARDRAIL_POLICY=<name> imitates infra/guardrails/<name>.json, so the class can see its effect offline.
"""

import base64
import json
import math
import os
import time
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

MODEL = os.getenv("FDE_MODEL", "anthropic/claude-sonnet-4.5")
FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


class LLMError(RuntimeError):
    """The model did not return valid JSON for the schema, even after one retry, or the platform refused the call."""


class RateLimited(LLMError):
    """The provider refused the call because too many were sent at once (HTTP 429, or Bedrock's ThrottlingException).
    retry_after is the number of seconds the provider asked us to wait, when it said (the Retry-After header)."""

    retry_after: float = 0.0


class GuardrailBlocked(LLMError):
    """The guardrail stopped the request (input) or the reply (output). The message is the guardrail's own text."""

    def __init__(self, where: str, message: str):
        super().__init__(f"Guardrail blocked the {where}: {message}")
        self.where = where
        self.message = message


def settings() -> dict:
    """The model settings in force now, read from the environment each time (so a test or a script can change them)."""
    return {
        "fake": os.getenv("FDE_FAKE_LLM") == "1",
        "provider": os.getenv("FDE_LLM_PROVIDER", "openrouter"),
        "region": os.getenv("FDE_BEDROCK_REGION", "eu-west-2"),
        "model_id": os.getenv("FDE_BEDROCK_MODEL_ID", "eu.anthropic.claude-haiku-5-5"),
        "guardrail_id": os.getenv("FDE_GUARDRAIL_ID", ""),
        "guardrail_version": os.getenv("FDE_GUARDRAIL_VERSION", ""),
        "guardrail_policy": os.getenv("FDE_GUARDRAIL_POLICY", ""),
        "openrouter_model": MODEL,
    }


class FakeLLM:
    """Scripted replies for FDE_FAKE_LLM=1: reply_for('findings') returns tests/fixtures/findings.json.
    With a guardrail policy set, the scripted guardrail is applied to every request and reply."""

    is_fake = True

    def __init__(self, guardrail_policy: str = ""):
        self.guardrail_policy = guardrail_policy
        self.calls: list[dict] = []

    @property
    def cache_tag(self) -> str:
        return f"guard-{self.guardrail_policy}" if self.guardrail_policy else ""

    def reply_for(self, task: str) -> str:
        return (FIXTURES / f"{task}.json").read_text(encoding="utf-8")


# ---------------------------------------------------------------- Amazon Bedrock (ticket ENG-501)
class BedrockClient:
    """One model on Amazon Bedrock, called with the Converse API.

    `runtime` is a boto3 "bedrock-runtime" client. The tests pass one wrapped in botocore's Stubber,
    so they check the exact request you send without calling AWS.
    """

    provider = "bedrock"

    def __init__(self, runtime, model_id: str, guardrail_id: str = "", guardrail_version: str = ""):
        self.runtime = runtime
        self.model_id = model_id
        self.guardrail_id = guardrail_id
        self.guardrail_version = guardrail_version
        self.calls: list[dict] = []  # one entry per call: input_tokens, output_tokens, latency_ms, stop_reason

    @property
    def cache_tag(self) -> str:
        tag = f"bedrock-{self.model_id}"
        return f"{tag}-guard-{self.guardrail_id}-{self.guardrail_version}" if self.guardrail_id else tag

    def request(self, system: str, messages: list[dict]) -> dict:
        """The Converse request for a system prompt and a list of {"role", "content"} messages (content is text)."""
        req = {
            "modelId": self.model_id,
            "system": [{"text": system}],
            "messages": [{"role": m["role"], "content": _converse_content(m["content"])} for m in messages],
            "inferenceConfig": {"temperature": 0, "maxTokens": 2000},
        }
        if self.guardrail_id:
            req["guardrailConfig"] = {"guardrailIdentifier": self.guardrail_id,
                                      "guardrailVersion": self.guardrail_version or "DRAFT", "trace": "enabled"}
        return req

    def complete(self, system: str, messages: list[dict]) -> str:
        """Send one Converse request and return the reply's text.

        - Send exactly self.request(system, messages).
        - The reply's text is every "text" block of output.message.content, joined with no separator.
        - Record one entry in self.calls: input_tokens and output_tokens from "usage", latency_ms from
          metrics.latencyMs, and stop_reason.
        - stopReason "guardrail_intervened": raise GuardrailBlocked("reply", <the reply's text>).
        - A botocore ClientError: raise LLMError naming its error code, with the hints in BEDROCK_HINTS.
        """
        from botocore.exceptions import ClientError

        try:
            started = time.perf_counter()
            r = self.runtime.converse(**self.request(system, messages))
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "ClientError")
            msg = e.response.get("Error", {}).get("Message", str(e))
            if code == "ThrottlingException":
                raise RateLimited(f"Bedrock {code}: {msg}") from e
            raise LLMError(f"Bedrock {code}: {msg}. {BEDROCK_HINTS.get(code, '')}".strip()) from e
        text = "".join(b.get("text", "") for b in r["output"]["message"]["content"])
        usage = r.get("usage", {})
        self.calls.append({"input_tokens": usage.get("inputTokens", 0), "output_tokens": usage.get("outputTokens", 0),
                           "latency_ms": r.get("metrics", {}).get("latencyMs", round((time.perf_counter() - started) * 1000)),
                           "stop_reason": r.get("stopReason", "")})
        if r.get("stopReason") == "guardrail_intervened":
            raise GuardrailBlocked("reply", text)
        return text


def _converse_content(content) -> list[dict]:
    """Text, or (Day 6) a list of parts: {"type": "text", "text": …} and {"type": "image", "jpeg": <bytes>}."""
    if isinstance(content, str):
        return [{"text": content}]
    return [{"text": p["text"]} if p["type"] == "text" else {"image": {"format": "jpeg", "source": {"bytes": p["jpeg"]}}} for p in content]


def _openai_content(content):
    if isinstance(content, str):
        return content
    return [{"type": "text", "text": p["text"]} if p["type"] == "text" else
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(p["jpeg"]).decode()}} for p in content]


BEDROCK_HINTS = {
    "AccessDeniedException": "Check that the model is enabled for your account in eu-west-2, and that your role allows bedrock:InvokeModel on it.",
    "ValidationException": "Check the model ID: in London, use an in-Region model ID (no 'eu.' or 'global.' prefix) that the Region serves.",
    "ResourceNotFoundException": "The model or guardrail ID does not exist in this Region.",
    "ThrottlingException": "Too many requests for your account's quota: wait a minute, or run fewer cases at once.",
}


class OpenRouterClient:
    """Days 1-4: the OpenAI SDK pointed at OpenRouter."""

    provider = "openrouter"
    cache_tag = ""

    def __init__(self, sdk):
        self.sdk = sdk
        self.calls: list[dict] = []
        self.chat = sdk.chat  # tests and older code call client.chat.completions.create directly

    def complete(self, system: str, messages: list[dict]) -> str:
        import openai

        msgs = [{"role": "system", "content": system}, *[{"role": m["role"], "content": _openai_content(m["content"])} for m in messages]]
        started = time.perf_counter()
        try:
            reply = self.sdk.chat.completions.create(model=MODEL, messages=msgs, temperature=0)
        except openai.RateLimitError as e:
            err = RateLimited(f"OpenRouter: too many requests ({e})")
            try:
                err.retry_after = min(float(e.response.headers.get("retry-after", 0)), 60.0)
            except (AttributeError, TypeError, ValueError):
                pass
            raise err from e
        u = getattr(reply, "usage", None)
        self.calls.append({"input_tokens": getattr(u, "prompt_tokens", 0) or 0, "output_tokens": getattr(u, "completion_tokens", 0) or 0,
                           "latency_ms": round((time.perf_counter() - started) * 1000)})
        return reply.choices[0].message.content or ""


def llm_client():
    s = settings()
    if s["fake"]:
        return FakeLLM(s["guardrail_policy"])
    if s["provider"] == "bedrock":
        import boto3

        return BedrockClient(boto3.client("bedrock-runtime", region_name=s["region"]), s["model_id"],
                             s["guardrail_id"], s["guardrail_version"])
    from openai import OpenAI

    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise LLMError("OPENROUTER_API_KEY is missing: add it to .env in the repository root")
    return OpenRouterClient(OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key))


def _json_text(text: str) -> str:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        raise ValueError("no JSON object found")
    return text[start : end + 1]


def _estimate_tokens(text: str) -> int:
    return max(1, round(len(text) / 4))  # about four characters a token, for scripted runs


def image_tokens(jpeg: bytes) -> int:
    """What a picture costs in input tokens: one token per 28 x 28 pixel patch (Claude's vision guide)."""
    from PIL import Image
    import io

    w, h = Image.open(io.BytesIO(jpeg)).size
    return math.ceil(w / 28) * math.ceil(h / 28)


def ask_json(client, system: str, user: str, schema: type[BaseModel], task: str, image: bytes | None = None) -> BaseModel:
    """Ask the model for one JSON object that matches `schema`. If the reply is not valid,
    send the error back once and ask again. `task` names the fixture used in fake mode.
    With `image` (JPEG bytes), the picture is sent with the text (Day 6's vision method)."""
    if getattr(client, "is_fake", False):
        text = client.reply_for(task)
        if client.guardrail_policy:
            from app.platform.guardrail import load_policy, scripted_guardrail

            text = scripted_guardrail(load_policy(client.guardrail_policy), user, text)
        tokens_in = _estimate_tokens(system + user) + (image_tokens(image) if image else 0)
        client.calls.append({"input_tokens": tokens_in, "output_tokens": _estimate_tokens(text), "scripted": True})
        return schema.model_validate_json(text)

    content = user if image is None else [{"type": "text", "text": user}, {"type": "image", "jpeg": image}]
    messages = [{"role": "user", "content": content}]
    last_error = ""
    for attempt in range(2):
        if hasattr(client, "complete"):
            text = client.complete(system, messages)
        else:  # an OpenAI-shaped client, as in the Day 1-4 tests
            reply = client.chat.completions.create(model=MODEL, messages=[{"role": "system", "content": system},
                                                   *[{"role": m["role"], "content": _openai_content(m["content"])} for m in messages]], temperature=0)
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
