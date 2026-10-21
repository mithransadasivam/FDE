"""Day 15: keep answering when a model is slow or down. Retry a failing call a few times, waiting a
little longer each time, then switch to a fallback model.

Done: is_retryable(), SimulatedOutage and the settings.
Also done: call_with_fallback() (Activity 4). Check it with tests/test_reliability.py.
"""

import os
import time

import openai
from dotenv import load_dotenv

load_dotenv()
RETRIES = int(
    os.getenv("LLM_RETRIES", "2")
)  # extra tries per model after the first one
BACKOFF = float(
    os.getenv("LLM_BACKOFF", "0.5")
)  # seconds before the first retry; doubles each time
TIMEOUT = float(os.getenv("LLM_TIMEOUT", "20"))  # seconds before a model call gives up


class ModelUnavailable(Exception):
    """Every model failed: the API answers 503 and asks the user to try again later."""


class SimulatedOutage(ConnectionError):
    """Raised on purpose when SIMULATE_OUTAGE names a model, so you can watch the fallback work."""


# Errors that may go away if you try again: a timeout, a dropped connection, too many requests
# (429) or a server error (5xx). A bad request (400) or a wrong key (401) will fail every time.
RETRYABLE = (
    openai.APITimeoutError,
    openai.APIConnectionError,
    openai.RateLimitError,
    openai.InternalServerError,
    TimeoutError,
    ConnectionError,
)


def is_retryable(error: Exception) -> bool:
    return isinstance(error, RETRYABLE)


def call_with_fallback(
    call,
    models: list[str],
    retries: int = RETRIES,
    backoff: float = BACKOFF,
    sleep=None,
) -> dict:
    """call(model) with retries, then the next model, until one works.

    Rules (tests/test_reliability.py checks each one):
    - sleep defaults to time.sleep (the tests pass their own, so they never wait)
    - errors = [], attempts = 0
    - for each model in models, in order, try up to 1 + retries times:
        attempts += 1
        result = call(model): success, return
            {"result": result, "model": model, "fallback": model != models[0], "attempts": attempts}
        an error where is_retryable(error) is True:
            errors.append(f"{model}: {type(error).__name__}")
            if this model has tries left: sleep(backoff * 2 ** n) where n is 0 after its first try,
            1 after its second ... (so 0.5, then 1.0 seconds); no sleep before moving to the next model
        any other error: raise it at once (retrying a bad request or a wrong key does not help)
    - every model failed: raise ModelUnavailable("; ".join(errors))
    """
    sleep = sleep or time.sleep
    errors = []
    attempts = 0
    for model in models:
        for n in range(1 + retries):
            attempts += 1
            try:
                result = call(model)
            except Exception as error:
                if not is_retryable(error):
                    raise
                errors.append(f"{model}: {type(error).__name__}")
                if n < retries:
                    sleep(backoff * 2**n)
                continue
            return {
                "result": result,
                "model": model,
                "fallback": model != models[0],
                "attempts": attempts,
            }
    raise ModelUnavailable("; ".join(errors))
