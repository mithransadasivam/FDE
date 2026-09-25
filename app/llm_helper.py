import logging
import os
import time

from dotenv import load_dotenv
from openai import OpenAI

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def ask_llm(prompt, model=None, temperature=0.2, client=None):
    if not prompt or not prompt.strip():
        raise ValueError("prompt must not be empty")

    load_dotenv()

    if model is None:
        model = os.getenv("LLM_MODEL")
        if not model:
            raise RuntimeError(
                "No model given and LLM_MODEL is not set. Pass model= or set LLM_MODEL in .env."
            )

    if client is None:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. Add it to your .env file or environment."
            )
        client = OpenAI(api_key=api_key, base_url=OPENROUTER_BASE_URL)

    start = time.perf_counter()
    try:
        response = client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception:
        logger.error("LLM call failed model=%s", model)
        raise
    latency_ms = round((time.perf_counter() - start) * 1000)
    total_tokens = getattr(getattr(response, "usage", None), "total_tokens", None)
    logger.info(
        "LLM call model=%s latency_ms=%d total_tokens=%s",
        model,
        latency_ms,
        total_tokens,
    )
    return (response.choices[0].message.content or "").strip()
