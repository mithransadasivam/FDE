"""An optional picture for an answer ("pictures out"). Off unless the person presses the button.

Only a one-sentence summary of the answer is sent to the picture model, never the question, the documents or any ticket, plus a fixed
style line that forbids text, numbers, logos and people. The picture is checked like any picture (real image, size), labelled as
AI-generated, and kept only in memory while the page is open.
"""
import re

from app.calllog import log_call
from app.config import ILLUSTRATIONS_ENABLED, ILLUSTRATION_STYLE, ILLUSTRATION_SUMMARY_CHARS, IMAGE_COST_USD
from app.images import ImageError, check_image
from app.llm import call_image

LABEL = "AI-generated illustration"
CODE = re.compile(r"\b[A-Z]{2,6}-\d{2,5}\b")


class IllustrationError(ValueError):
    """No picture can be made for this answer. The message is friendly and safe to show."""


def summary_of(answer_text: str) -> str:
    """One short sentence taken from the answer: citation marks removed, error codes and addresses dropped, capped in length."""
    text = re.sub(r"[*_`#]", "", re.sub(r"\[\d+\]", "", answer_text or ""))  # citation marks and markdown marks
    text = re.sub(r"https?://\S+|\S+@\S+", "", text)
    text = CODE.sub("", text)
    lines =[" ".join(line.split()) for line in text.splitlines()]
    sentences = [s.strip(" *-#") for line in lines if not re.match(r"^\s*(\d+\.|[-*•])\s", line) for s in re.split(r"(?<=[.!?])\s+", line)]  # list items are steps, not a summary
    sentences = [re.sub(r"\s+([.,;:!?])", r"\1", s) for s in sentences if s and not s.endswith(":") and not s.endswith(" :")]  # an intro like "follow these steps:" says nothing
    first = sentences[0][:ILLUSTRATION_SUMMARY_CHARS].strip() if sentences else ""
    first = re.sub(r"\s+([.,;:!?])", r"\1", " ".join(re.sub(r"\d[\d:.,]*\d|\d", "", first).split()))  # a number in the summary gets drawn as a number ("floor 4" gave a big 4), so none is sent
    if len(re.findall(r"[A-Za-z]{3,}", first)) < 3:
        raise IllustrationError("There is not enough in that answer to draw a picture of.")
    return first


def prompt_for(answer_text: str) -> str:
    return f"{summary_of(answer_text)} {ILLUSTRATION_STYLE}"


def illustrate(answer_text: str, draw=call_image, enabled: bool = ILLUSTRATIONS_ENABLED) -> dict:
    """Make one picture for an answer. Returns {image, label, summary, cost_usd}. Raises IllustrationError (or LLMError if unreachable)."""
    if not enabled:
        raise IllustrationError("Pictures are switched off.")  # checked before anything is built or sent
    prompt = prompt_for(answer_text)
    picture = draw(prompt)
    try:
        check_image(picture)
    except ImageError as err:
        raise IllustrationError("The picture model did not return a usable picture. Please try again.") from err
    log_call({"kind": "illustration", "image_calls": 1, "cost_usd": IMAGE_COST_USD, "prompt_chars": len(prompt)})
    return {"image": picture, "label": LABEL, "summary": summary_of(answer_text), "cost_usd": IMAGE_COST_USD}
