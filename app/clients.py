"""Ready-made model clients for Day 3. You do not need to change this file.

hosted_client() talks to OpenRouter; local_client() talks to Ollama on your laptop.
Both return the same kind of client, so the rest of the code does not care which it gets.
"""

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
HOSTED_MODEL = os.getenv("LLM_MODEL", "anthropic/claude-haiku-4.5")
LOCAL_MODEL = os.getenv("LOCAL_MODEL", "llama3.2")


def hosted_client() -> OpenAI:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set; add it to .env")
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)


def local_client() -> OpenAI:
    # Ollama ignores the key, but the library requires one
    return OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
