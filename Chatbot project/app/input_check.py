"""Input checks that run BEFORE any search or model call: empty, meaningless and very long input.

No model is used here, so a bad input costs nothing and cannot invent an answer.

The choices (written in EVAL_REPORT.md):
- Empty or only spaces: ask the user to type a question.
- No recognisable words (an emoji, random characters, keyboard mashing): ask the user to type the question in words.
  A word counts if it is common English, appears in the documents, or simply looks like a word. So codes such as VPN-809,
  one-word questions like "salary?" and questions in another language still go through to be answered or declined.
- Longer than MAX_QUESTION_CHARS: keep the END. A pasted log or email usually has the question last. The chatbot then says it did that.
- Longer than MAX_INPUT_CHARS: refused, because pasting that much is almost certainly a mistake.
- A question in another language is searched as it is and answered in English from the English documents.
"""
import re
from functools import lru_cache

from app.config import DOCS_DIR, MAX_INPUT_CHARS, MAX_QUESTION_CHARS

MSG_EMPTY = "Please type a question."
MSG_NOT_A_QUESTION = "I could not find any words to search for. Please type your question in words."
MSG_TOO_LONG = f"That message is far too long (over {MAX_INPUT_CHARS:,} characters). Please paste only the part that matters."
KEEP_LAST = 300  # when a long message has no clear final question, keep about this much of its end

COMMON_WORDS = frozenset("""
a about after again all also am an and any are as at be been before but by can could did do does doing for from get got
had has have he her here him his how i if in into is it its just like me more my need no not now of on one or other our
out she should so some such than that the their them then there these they this to too up us was we were what when where
which who why will with would you your hi hello hey please thanks thank help yes ok okay
""".split())


@lru_cache(maxsize=1)
def document_vocabulary() -> frozenset:
    """Every word of two or more letters that appears in the knowledge-base documents (built once, then cached)."""
    from app.loader import load_documents
    words = set()
    for doc in load_documents(DOCS_DIR):
        for page in doc.get("pages", []):
            text = page[1] if isinstance(page, (tuple, list)) else page.get("text", "")
            words.update(w for w in re.findall(r"[a-z]{2,}", text.lower()))
    return frozenset(words)


def shorten(text: str, limit: int = MAX_QUESTION_CHARS) -> str:
    """Cut a long message down to its end. If the end is a question, keep that question.

    A very short last question ("And for P3?") keeps the sentence before it, so it still makes sense.
    """
    if len(text) <= limit:
        return text
    tail = text[-limit:]
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", tail) if p.strip()]
    if len(parts) > 1:
        parts = parts[1:]  # the first piece of the tail was probably cut in the middle
    if not parts:
        return tail.strip()
    last = parts[-1]
    if last.endswith("?"):
        return (parts[-2] + " " + last) if len(last) < 25 and len(parts) > 1 else last
    kept = []
    for part in reversed(parts):
        if sum(len(p) + 1 for p in kept) + len(part) > KEEP_LAST and kept:
            break
        kept.insert(0, part)
    return " ".join(kept)


KEYBOARD_ROWS = ("qwertyuiop", "asdfghjkl", "zxcvbnm")


def looks_like_a_word(token: str) -> bool:
    """A made-up token still counts as a word if it has letters and a vowel and is not a run along the keyboard."""
    if len(token) < 3 or not re.fullmatch(r"[a-z]+", token) or not re.search(r"[aeiouy]", token):
        return False
    return not any(token in row or token[::-1] in row for row in KEYBOARD_ROWS)


def has_recognisable_words(text: str, vocabulary=None) -> bool:
    """True when at least one word is known (common English, or in the documents) or at least looks like a real word.

    So "salary?" and "Kubernetes?" go on to be declined properly, while "asdf qwer zxcv", "12345 !!@@##" and an emoji do not.
    """
    known = COMMON_WORDS | (document_vocabulary() if vocabulary is None else frozenset(vocabulary))
    tokens = re.findall(r"[a-z]{2,}", text.lower())
    return any(t in known or looks_like_a_word(t) for t in tokens)


def check_input(raw: str, vocabulary=None) -> dict:
    """Decide what to do with what the user typed.

    Returns {action: "ask" or "ok", text, message, reason, shortened_to}.
    - "ask": do not search; show `message`.
    - "ok": search for `text` (the input, shortened if it was long). `shortened_to` is set only when it was cut.
    """
    text = (raw or "").strip()
    if not text:
        return {"action": "ask", "text": "", "message": MSG_EMPTY, "reason": "empty question", "shortened_to": ""}
    if len(text) > MAX_INPUT_CHARS:
        return {"action": "ask", "text": "", "message": MSG_TOO_LONG, "reason": "message far too long", "shortened_to": ""}
    shortened_to = ""
    if len(text) > MAX_QUESTION_CHARS:
        text = shorten(text)
        shortened_to = text
    if not has_recognisable_words(text, vocabulary):
        return {"action": "ask", "text": "", "message": MSG_NOT_A_QUESTION, "reason": "no recognisable words", "shortened_to": ""}
    return {"action": "ok", "text": text, "message": "", "reason": "", "shortened_to": shortened_to}
