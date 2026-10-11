"""Asking about a screenshot: read the error off the picture, search the documents for it, and answer from the documents.

Two steps, the same shape as a typed question:
  1. the vision model reads the error code and the application from the (resized) picture;
  2. the normal search then looks for that code in the documents and the normal answer path writes the answer, so every guard still
     applies and the answer cites the documents, never the picture.
If the picture shows no readable error code, or is not an IT error screen at all, the answer is the usual decline: never an invented fix.
"""
import time

from app.answer import _result, answer_stream, usage_snapshot
from app.calllog import log_call
from app.config import DECLINE_SENTENCE, IMAGE_MAX_SIDE, RETRIEVAL_MODE, TOP_K
from app.images import ImageError, check_image, resize_for_model
from app.llm import LLMError, call_vision, stream_model
from app.hybrid import hybrid_search
from app.vision import VisionError, read_screenshot

DEFAULT_QUESTION = "What does this error mean and what do I do?"
STATUS_READING = "Reading the screenshot…"


def default_reader(vision=call_vision):
    """A reader that asks the vision model: reader(picture bytes, mime type, file name) -> reading."""
    return lambda image, mime, filename: read_screenshot(image, mime, vision)


def real_retriever(query: str):
    """Search the documents for the code the picture shows. Exact codes are what keyword search is good at (Part 2), so this is the
    hybrid search, and the query is just "error code <CODE>": adding the application's name made the right chunk drop out of the top
    four for two of the eight codes."""
    def retrieve(question: str, k: int):
        return {"chunks": hybrid_search(query, k), "searched_for": query}
    return retrieve


def answer_image_stream(question: str, image: bytes, filename: str = "", reader=None, stream=stream_model, retriever_for=real_retriever,
                        previous_question: str = "", max_side: int = IMAGE_MAX_SIDE, mode: str | None = None):
    """Like `answer_stream`, for a question with a picture. Yields ("status", text), ("piece", text) ... then ("done", result).

    `result` has everything `answer_stream` gives, plus `image` = what was read ({error_code, application, ...}) and `image_info`
    (type, bytes before and after resizing, pixels), so the page can say what it saw. A file that is not a usable picture gives a
    friendly "done" result with no model call. Raises LLMError / VisionError if the vision model cannot be reached or understood.
    """
    reader = reader or default_reader()
    started = time.perf_counter()
    before = usage_snapshot()
    try:
        small, mime, size = resize_for_model(image, max_side)
    except ImageError as err:
        result = _result(str(err), [], False, 0.0, 0, started, "image: not usable")
        result.update(image=None, image_info=None, first_words_seconds=result["seconds"])
        yield "done", result
        return
    info = {"type": check_image(image), "bytes_in": len(image), "bytes_sent": len(small), "pixels": f"{size[0]}x{size[1]}"}
    yield "status", STATUS_READING
    try:
        reading = reader(small, mime, filename)
    except Exception as err:
        log_call({"mode": mode or RETRIEVAL_MODE, "seconds": None, "outcome": "error", "error": type(err).__name__, "image": info,
                  **{k: v for k, v in _delta(before).items()}})
        raise

    if not reading["is_it_error_screen"] or not reading["error_code"]:
        reason = "image: not an IT error screen" if not reading["is_it_error_screen"] else (
            "image: too small or blurred to read" if not reading["legible"] else "image: no error code shown")
        result = _result(DECLINE_SENTENCE, [], True, 0.0, 0, started, reason)
        result.update(image=reading, image_info=info, first_words_seconds=result["seconds"])
        log_call({"mode": mode or RETRIEVAL_MODE, "seconds": result["seconds"], "first_words_seconds": result["seconds"], "outcome": "declined",
                  "error": "", "chunks_used": 0, "image": info, **_delta(before)})
        yield "done", result
        return

    code, application = reading["error_code"], reading["application"]
    query = f"error code {code}"
    user_words = question.strip() or DEFAULT_QUESTION
    # Only the validated code goes to the answer model. The application name (free text read from a picture) is used for the search
    # query and for the caption on the page, never inside the prompt, so a picture cannot slip words into it that way.
    question_for_model = f"The screenshot shows error {code}. {user_words}"
    inner, code_missing = retriever_for(query), []

    def retriever(question: str, k: int):
        """No guessing: if none of the retrieved chunks actually contains the code the picture showed, there is nothing to answer from."""
        found = inner(question, k)
        if not any(code in chunk["text"].upper() for chunk in found["chunks"]):
            code_missing.append(True)
            return {"chunks": [], "searched_for": found["searched_for"]}
        return found

    for kind, value in answer_stream(question_for_model, retriever=retriever, stream=stream, previous_question=previous_question,
                                     mode=mode, usage_since=before, started_at=started, log_extra={"image": info}):
        if kind == "done":
            value["image"], value["image_info"] = reading, info
            if code_missing:
                value["reason"] = "image: no document mentions that code"
        yield kind, value


def _delta(before: dict) -> dict:
    after = usage_snapshot()
    keys = ("input_tokens", "output_tokens", "vision_calls", "vision_input_tokens", "vision_output_tokens")
    return {key: after[key] - before[key] for key in keys} | {"model_calls": after["calls"] - before["calls"]}
