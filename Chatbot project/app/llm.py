"""The hosted answer model, called through OpenRouter."""
import os

import requests
from dotenv import load_dotenv

from app.config import LLM_TIMEOUT, MAX_TOKENS, ROOT, TEMPERATURE

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class LLMError(RuntimeError):
    """The answer model is not configured, unreachable or returned something unusable."""


def call_model(messages: list[dict]) -> str:
    """Send chat messages to the model named by LLM_MODEL and return the reply text."""
    load_dotenv(ROOT / ".env")
    key, model = os.getenv("OPENROUTER_API_KEY"), os.getenv("LLM_MODEL")
    if not key or not model:
        raise LLMError("The answer model is not configured. Check OPENROUTER_API_KEY and LLM_MODEL in .env.")
    try:
        resp = requests.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "messages": messages, "temperature": TEMPERATURE, "max_tokens": MAX_TOKENS},
            timeout=LLM_TIMEOUT,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise ValueError("empty or non-text reply")  # e.g. content: null on a refusal
        return content.strip()
    except (requests.RequestException, KeyError, IndexError, ValueError, TypeError, AttributeError) as err:
        # Only the error type is reported: never the request, which holds the key.
        raise LLMError(f"The answer model could not be reached ({type(err).__name__}). Please try again.") from err
