# HW #2

Code lives at the repo root so imports and `pytest -q` work; it is reproduced
below so this folder is self-contained. Run `pytest -q` from the repo root.

## Task 1: logging in `ask_llm`
Logs model, latency (ms) and total tokens at INFO. On API failure logs the
model at ERROR and re-raises. Never logs the prompt, reply or API key.
Files: `app/llm_helper.py`, `tests/test_llm_helper.py`.

```python
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
```

## Task 2: test the error cases
Tests added to `tests/test_llm_helper.py` before touching the code:
1. `test_client_exception_is_logged_as_error_and_reraised`: client raises, `ask_llm` logs at ERROR and re-raises.
2. `test_model_returning_none_gives_empty_string_not_crash`: `None` content returns `""`.
3. `test_prompt_of_only_spaces_raises_value_error`: spaces-only prompt raises `ValueError`.

Result: all three passed on the first run (18 passed), so no test failed first and
`app/llm_helper.py` needed no change. The Task 1 logging code already re-raised
after logging, and the original code already handled `None` content and blank prompts.
Tests were not modified to pass.

## Task 3: fix a colleague's script
Files: `tools/log_parser.py`, `data/sample.log` (includes a blank line),
`tests/test_log_parser.py` (expects `{"INFO": 1, "WARNING": 1, "ERROR": 2}`).

- Bug 1: blank line -> `IndexError` from `line.split()[1]`. Fix: skip lines with fewer than two words.
- Bug 2: `counts[level] =+ 1` assigns +1 instead of adding, so ERROR counted 1, not 2. Fix: `+= 1`.

```python
# tools/log_parser.py
def count_levels(lines):
    counts = {"INFO": 0, "WARNING": 0, "ERROR": 0}
    for line in lines:
        parts = line.split()
        if len(parts) < 2:
            continue
        level = parts[1]
        if level in counts:
            counts[level] += 1
    return counts
```
