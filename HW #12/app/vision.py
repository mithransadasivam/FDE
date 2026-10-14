"""Day 10: send images to a model that can see them.

load_image(), image_message(), ask_about_image() and estimate_image_tokens() are done.
Activity 1: fill in image_part(). Check it with tests/test_vision.py.
"""

import base64  # noqa: F401  (you will need it)
import os
from pathlib import Path

from dotenv import load_dotenv

from app.rag import llm_client

load_dotenv()
VISION_MODEL = os.getenv(
    "VISION_MODEL", os.getenv("LLM_MODEL", "anthropic/claude-haiku-4.5")
)
MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}
MAX_BYTES = 5 * 1024 * 1024  # 5 MB: a common limit for one image


def load_image(path) -> tuple[bytes, str]:
    """Read an image file. Returns (the bytes, the MIME type, e.g. "image/png")."""
    path = Path(path)
    mime = MIME_TYPES.get(path.suffix.lower())
    if mime is None:
        raise ValueError(
            f"{path.name}: not a supported image type ({', '.join(MIME_TYPES)})"
        )
    data = path.read_bytes()
    if len(data) > MAX_BYTES:
        raise ValueError(
            f"{path.name}: {len(data)} bytes is over the {MAX_BYTES} byte limit"
        )
    return data, mime


def image_part(data: bytes, mime: str) -> dict:
    """TODO (Activity 1): turn image bytes into the piece of a message a vision model reads.

    Rules (tests/test_vision.py checks each one):
    - if mime is not one of the values in MIME_TYPES, raise ValueError
    - if data is empty, raise ValueError
    - encode the bytes as base64 text: base64.b64encode(data).decode("ascii")
    - return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}}
    """
    if mime not in MIME_TYPES.values():
        raise ValueError(f"unsupported image type: {mime}")
    if not data:
        raise ValueError("the image is empty")
    encoded = base64.b64encode(data).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}}


def image_message(prompt: str, *parts: dict) -> dict:
    """One user message with the text first, then one or more image parts."""
    return {"role": "user", "content": [{"type": "text", "text": prompt}, *parts]}


def ask_about_image(path, prompt: str, client=None, model: str = VISION_MODEL) -> str:
    """Send one image and a question; return the model's reply."""
    data, mime = load_image(path)
    client = client or llm_client()
    reply = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[image_message(prompt, image_part(data, mime))],
    )
    return (reply.choices[0].message.content or "").strip()


def estimate_image_tokens(width: int, height: int) -> int:
    """A rough guide to how many input tokens an image costs: width x height / 750
    (the guide Anthropic publishes for Claude models; other providers count differently)."""
    return round(width * height / 750)
