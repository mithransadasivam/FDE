"""The hosted models, called through OpenRouter: the answer model, and the judge used only by evaluation scripts."""
import json
import os

import requests
from dotenv import load_dotenv

from app.config import VISION_MAX_TOKENS, JUDGE_MAX_TOKENS, JUDGE_TEMPERATURE, LLM_TIMEOUT, MAX_TOKENS, ROOT, TEMPERATURE

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class LLMError(RuntimeError):
    """The answer model is not configured, unreachable or returned something unusable."""


# A running count of model calls and tokens, so evaluation scripts can measure one question at a time:
# reset_usage(), ask, then usage_snapshot(). Nothing in the app depends on it.
# The "critic" counters are the self-critique reviews (they use the judge model, which has its own price).
USAGE = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "critic_calls": 0, "critic_input_tokens": 0, "critic_output_tokens": 0,
         "vision_calls": 0, "vision_input_tokens": 0, "vision_output_tokens": 0}  # "vision": the model that reads images (VISION_MODEL)


def reset_usage() -> None:
    USAGE.update({key: 0 for key in USAGE})


def usage_snapshot() -> dict:
    return dict(USAGE)


def _record_usage(data: dict, prefix: str = "") -> None:
    """Add one call and the token counts the provider reported (zero when it reports none). `prefix` picks the counters."""
    usage = data.get("usage") if isinstance(data, dict) else None
    usage = usage if isinstance(usage, dict) else {}
    USAGE[f"{prefix}calls"] += 1
    for key, field in (("input_tokens", "prompt_tokens"), ("output_tokens", "completion_tokens")):
        value = usage.get(field)
        USAGE[f"{prefix}{key}"] += value if isinstance(value, int) and value > 0 else 0


def _chat(messages: list[dict], model_variable: str, temperature: float, max_tokens: int, who: str, usage_prefix: str | None = "") -> str:
    """Send chat messages to the model named in .env by `model_variable` and return the reply text."""
    load_dotenv(ROOT / ".env")
    key, model = os.getenv("OPENROUTER_API_KEY"), os.getenv(model_variable)
    if not key or not model:
        raise LLMError(f"The {who} is not configured. Check OPENROUTER_API_KEY and {model_variable} in .env.")
    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
            timeout=LLM_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        if usage_prefix is not None:
            _record_usage(data, usage_prefix)
        content = data["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError("empty or non-text reply")  # e.g. content: null on a refusal
        return content.strip()
    except (requests.RequestException, KeyError, IndexError, ValueError, TypeError, AttributeError) as err:
        # Only the error type is reported: never the request, which holds the key.
        raise LLMError(f"The {who} could not be reached ({type(err).__name__}). Please try again.") from err


def call_model(messages: list[dict]) -> str:
    """Send chat messages to the answer model named by LLM_MODEL and return the reply text."""
    return _chat(messages, "LLM_MODEL", TEMPERATURE, MAX_TOKENS, "answer model")


def call_judge(messages: list[dict]) -> str:
    """Send chat messages to the judge model named by JUDGE_MODEL (not counted in the chatbot's token usage)."""
    return _chat(messages, "JUDGE_MODEL", JUDGE_TEMPERATURE, JUDGE_MAX_TOKENS, "judge model", usage_prefix=None)


def call_critic(messages: list[dict]) -> str:
    """The judge model used as a reviewer inside the chatbot (self-critique). Its tokens are counted separately."""
    return _chat(messages, "JUDGE_MODEL", JUDGE_TEMPERATURE, JUDGE_MAX_TOKENS, "judge model", usage_prefix="critic_")


def stream_model(messages: list[dict]):
    """Yield the answer model's reply piece by piece as it arrives (server-sent events), for the chat tab.

    Same model, temperature and limits as `call_model`. Empty pieces are skipped. If the connection fails at any point,
    even halfway through, an LLMError is raised: the caller never gets a half answer without knowing it.
    """
    load_dotenv(ROOT / ".env")
    key, model = os.getenv("OPENROUTER_API_KEY"), os.getenv("LLM_MODEL")
    if not key or not model:
        raise LLMError("The answer model is not configured. Check OPENROUTER_API_KEY and LLM_MODEL in .env.")
    try:
        with requests.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "messages": messages, "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS,
                  "stream": True, "stream_options": {"include_usage": True}},
            timeout=LLM_TIMEOUT,
            stream=True,
        ) as resp:
            resp.raise_for_status()
            resp.encoding = "utf-8"
            usage_data = None
            for line in resp.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data:"):
                    continue  # blank separators and ": OPENROUTER PROCESSING" comments
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                data = json.loads(payload)
                if isinstance(data, dict) and isinstance(data.get("usage"), dict):
                    usage_data = data
                choices = data.get("choices") if isinstance(data, dict) else None
                if not choices:
                    continue
                piece = (choices[0].get("delta") or {}).get("content")
                if isinstance(piece, str) and piece:
                    yield piece
            if usage_data is not None:
                _record_usage(usage_data)
    except (requests.RequestException, KeyError, IndexError, ValueError, TypeError, AttributeError) as err:
        raise LLMError(f"The answer model could not be reached ({type(err).__name__}). Please try again.") from err


def call_vision(messages: list[dict], max_tokens: int = VISION_MAX_TOKENS) -> str:
    """Send a message that includes an image to the vision model named by VISION_MODEL. Its tokens are counted as "vision"."""
    return _chat(messages, "VISION_MODEL", 0.0, max_tokens, "vision model", usage_prefix="vision_")


STT_URL = "https://openrouter.ai/api/v1/audio/transcriptions"
USAGE.update({"stt_calls": 0, "stt_seconds": 0.0})


def call_stt(audio: bytes, fmt: str, seconds: float = 0.0) -> str:
    """Turn a recording into text with the speech-to-text model named by STT_MODEL. Returns the text (possibly empty for silence)."""
    import base64
    load_dotenv(ROOT / ".env")
    key, model = os.getenv("OPENROUTER_API_KEY"), os.getenv("STT_MODEL")
    if not key or not model:
        raise LLMError("The speech model is not configured. Check OPENROUTER_API_KEY and STT_MODEL in .env.")
    try:
        resp = requests.post(STT_URL, headers={"Authorization": f"Bearer {key}"}, timeout=LLM_TIMEOUT,
                             json={"model": model, "input_audio": {"data": base64.b64encode(audio).decode("ascii"), "format": fmt}})
        resp.raise_for_status()
        text = resp.json()["text"]
        if not isinstance(text, str):
            raise ValueError("no text")
        USAGE["stt_calls"] += 1
        USAGE["stt_seconds"] += seconds
        return text.strip()
    except (requests.RequestException, KeyError, ValueError, TypeError, AttributeError) as err:
        raise LLMError(f"The speech model could not be reached ({type(err).__name__}). Please try again.") from err


IMAGE_URL = "https://openrouter.ai/api/v1/images"
USAGE.update({"image_calls": 0})


def call_image(prompt: str) -> bytes:
    """Draw one picture with the model named by IMAGE_MODEL. Returns the picture bytes."""
    import base64
    load_dotenv(ROOT / ".env")
    key, model = os.getenv("OPENROUTER_API_KEY"), os.getenv("IMAGE_MODEL")
    if not key or not model:
        raise LLMError("The picture model is not configured. Check OPENROUTER_API_KEY and IMAGE_MODEL in .env.")
    try:
        resp = requests.post(IMAGE_URL, headers={"Authorization": f"Bearer {key}"}, json={"model": model, "prompt": prompt}, timeout=LLM_TIMEOUT * 2)
        resp.raise_for_status()
        picture = base64.b64decode(resp.json()["data"][0]["b64_json"], validate=True)
        if not picture:
            raise ValueError("empty picture")
        USAGE["image_calls"] += 1
        return picture
    except (requests.RequestException, KeyError, IndexError, ValueError, TypeError, AttributeError) as err:
        raise LLMError(f"The picture model could not be reached ({type(err).__name__}). Please try again.") from err
