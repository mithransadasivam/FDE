"""A fake chatbot for fast, repeatable browser tests. Off by default; `CHAT_FAKE=1` turns it on.

It replaces only the two things that need models: the search (no Ollama) and the answer writer (no hosted model). Everything
else is the REAL code: the input checks, the safety check, Guard 1, the output guard, the refusal and decline checks, the
citation check and the streaming path. So a browser test of "an unsafe request is refused" or "a decline has no sources" still
means something, and only the *content* of an answer is fake: a few fixed topics with fixed sources.

The fake never calls a model, a search, a key or the network. Anything outside its topics scores low, so the real Guard 1
declines it, exactly as the real chatbot declines what the documents do not cover.
"""
import csv
import re
import time
from pathlib import Path

from app.answer import answer_stream
from app.config import CHAT_FAKE_DELAY, ROOT
from app.followup import looks_like_follow_up
from app.screenshot import answer_image_stream

# keywords (lower case, any of them) -> one fixed source and one fixed answer. Several keywords hit = a stronger match.
TOPICS = [
    {"name": "vpn session", "keywords": ["vpn session", "stay connected", "session limit", "12 hours"],
     "source": "vpn_setup_guide.md", "page": 1, "text": "The VPN disconnects automatically after 12 hours. Reconnect and sign in again.",
     "answer": "A VPN session stays connected for up to 12 hours [1]. After that you reconnect and sign in again [1]."},
    {"name": "vpn install", "keywords": ["install the vpn", "vpn client", "northlink", "windows", "mac", "macbook"],
     "source": "vpn_setup_guide.md", "page": 1, "text": "Install NorthLink VPN from the company portal, approve the system extension on a Mac, then sign in.",
     "answer": "Install the NorthLink VPN client from the company portal [1]. On a Mac, approve the system extension and restart once [1].",
     "query": "VPN client install"},
    {"name": "vpn dropping", "keywords": ["cutting out", "keeps disconnecting", "drops", "disconnect"],
     "source": "vpn_troubleshooting.md", "page": 1, "text": "Update NorthLink to 5.2 or later, move closer to the router, and switch the protocol from Auto to TCP.",
     "answer": "Update NorthLink to version 5.2 or later [1]. Move closer to the router or use a cable [1]. Switch the protocol from Auto to TCP [1]."},
    {"name": "mfa", "keywords": ["mfa", "authenticator", "new phone", "multi-factor"],
     "source": "mfa_setup_guide.md", "page": 1, "text": "Raise a Reset MFA ticket first, then install the authenticator app and scan the QR code.",
     "answer": "Raise a Reset MFA ticket first [1]. Then install the authenticator app and scan the QR code [1]."},
    {"name": "backups", "keywords": ["backup", "backups"],
     "source": "backup_and_recovery_runbook.md", "page": 1, "text": "Daily backups run at 02:00 and are kept for 30 days.",
     "answer": "Daily server backups are kept for 30 days [1]."},
    {"name": "email", "keywords": ["email", "attachment", "mailbox"],
     "source": "email_and_calendar_faq.md", "page": 1, "text": "The email attachment limit is 25 MB. For larger files, share a NorthDrive link.",
     "answer": "The attachment limit is 25 MB [1]. For larger files, share a NorthDrive link [1]."},
    {"name": "priorities", "keywords": ["p1", "p2", "p3", "priority", "response target"],
     "source": "Day06_Slide15_policy_it_support_slas.pdf", "page": 2, "text": "P1: response within 15 minutes. P3: response within 4 hours.",
     "answer": "A P1 ticket gets a response within 15 minutes [1]. A P3 ticket gets a response within 4 hours [1]."},
]
MATCH_SCORE = 0.9      # a matched topic scores well above the minimum score
NO_MATCH_SCORE = 0.2   # anything else scores far below it, so the real Guard 1 declines


def _words(text: str) -> str:
    return " " + " ".join(re.findall(r"[a-z0-9]+", text.lower())) + " "


def _matches(keywords: list[str], text: str) -> int:
    haystack = _words(text)
    return sum(1 for kw in keywords if _words(kw) in haystack)


def pick_topic(question: str, previous_question: str = "") -> dict | None:
    """The best topic for a question. Words in the question count double; the previous question only helps with follow-ups."""
    best, best_score = None, 0
    for topic in TOPICS:
        score = 2 * _matches(topic["keywords"], question) + _matches(topic["keywords"], previous_question)
        if _matches(topic["keywords"], question) and score > best_score:
            best, best_score = topic, score
        elif best is None and score > best_score and previous_question and looks_like_follow_up(question):
            best, best_score = topic, score  # only a question that LOOKS like a follow-up borrows the previous question's topic
    return best


def fake_retriever(previous_question: str = "", chosen: dict | None = None):
    """A retriever for `answer_stream` that never searches: it returns the fixed chunk of the best topic and what it 'searched for'.

    The topic it picks is also stored in `chosen["topic"]`, so the fake answer writer says what the search found.
    """
    def retrieve(question: str, k: int):
        topic = pick_topic(question, previous_question)
        if chosen is not None:
            chosen["topic"] = topic
        if topic is None:
            return {"chunks": [{"text": "Nothing relevant.", "source": "none.md", "page": 1, "score": NO_MATCH_SCORE}], "searched_for": question}
        query = topic.get("query", topic["name"])
        searched = f"{query} {question.strip().rstrip('?')}" if previous_question and looks_like_follow_up(question) else question
        return {"chunks": [{"text": topic["text"], "source": topic["source"], "page": topic["page"], "score": MATCH_SCORE}], "searched_for": searched}
    return retrieve


def fake_stream(chosen: dict, delay: float = CHAT_FAKE_DELAY):
    """A stand-in for the model: writes the topic's fixed answer a word at a time, pausing between words."""
    def stream(messages):
        topic = chosen.get("topic")
        text = topic["answer"] if topic else "I do not know."
        words = text.split(" ")
        for n, word in enumerate(words):
            if delay:
                time.sleep(delay)
            yield word + ("" if n == len(words) - 1 else " ")
    return stream


def fake_answer_stream(question: str, previous_question: str = "", delay: float = CHAT_FAKE_DELAY, **_ignored):
    """The fake's version of `answer_stream`: the same events ("piece", ... then "done", result), the same real checks and guards."""
    chosen = {}
    yield from answer_stream(question, retriever=fake_retriever(previous_question, chosen), stream=fake_stream(chosen, delay),
                             previous_question=previous_question, mode="fake")


# --- screenshots: a fake picture reader, so a browser test can attach a picture with no models at all ----------------------------------

SUITE_CSV = ROOT / "data" / "multimodal_suite.csv"


def _screenshot_rows() -> dict:
    """The suite's screenshot rows by file name (the fake 'recognises' these pictures by name, like a lookup in the answer key)."""
    try:
        with open(SUITE_CSV, newline="", encoding="utf-8") as f:
            return {Path(r["file"]).name: r for r in csv.DictReader(f) if r["kind"] == "screenshot"}
    except OSError:
        return {}


def fake_reader(filename: str):
    """A stand-in for the vision model. A known picture gives the answer key's reading; an unknown one shows no error code."""
    def read(image: bytes, mime: str, name: str) -> dict:
        row = _screenshot_rows().get(Path(filename).name)
        if row is None:
            return {"is_it_error_screen": True, "error_code": "", "application": "", "legible": True}
        if row["expected_error_code"]:
            return {"is_it_error_screen": True, "error_code": row["expected_error_code"], "application": row["expected_application"], "legible": True}
        answer = row["expected_answer"].lower()
        return {"is_it_error_screen": "landscape" not in answer, "error_code": "", "application": "", "legible": "clearer picture" not in answer}
    return read


def fake_image_answer_stream(question: str, image: bytes, filename: str, previous_question: str = "", delay: float = CHAT_FAKE_DELAY, **_ignored):
    """The fake's version of `answer_image_stream`: a fake picture reader, a fixed chunk for the code, a slow fixed answer; every real check stays."""
    chosen = {}

    def retriever_for(query: str):
        code = query.split()[-1]
        row = next((r for r in _screenshot_rows().values() if r["expected_error_code"] == code), None)
        chosen["row"] = row

        def retrieve(q: str, k: int):
            if row is None:
                return {"chunks": [], "searched_for": query}
            return {"chunks": [{"text": f"{code}: {row['expected_answer']}", "source": row["expected_source"], "page": 1, "score": MATCH_SCORE}], "searched_for": query}
        return retrieve

    def stream(messages):
        row = chosen.get("row")
        words = (row["expected_answer"] + " [1]" if row else "I do not know.").split(" ")
        for n, word in enumerate(words):
            if delay:
                time.sleep(delay)
            yield word + ("" if n == len(words) - 1 else " ")

    yield from answer_image_stream(question, image, filename, reader=fake_reader(filename), stream=stream, retriever_for=retriever_for,
                                   previous_question=previous_question, mode="fake")


def fake_ticket(filename: str) -> dict:
    """A stand-in for `make_ticket_logged`: the answer key's ticket for a known picture. An unknown or code-less picture cannot make a ticket."""
    from app.ticket import TicketError
    row = _screenshot_rows().get(Path(filename).name)
    if row is None or not row["expected_error_code"]:
        raise TicketError("I could not make a ticket from that picture. Please try another screenshot, or describe the problem in words.")
    sentences = re.split(r"(?<=[.!?])\s+", row["expected_answer"])
    return {"error_code": row["expected_error_code"], "application": row["expected_application"], "summary": sentences[0][:160],
            "severity": row["expected_severity"], "next_step": " ".join(sentences[1:])[:300] or sentences[0][:300],
            "next_step_source": f"{row['expected_source']} p.1", "calls": 1}


def fake_vision(messages, max_tokens=None) -> str:
    """A stand-in for the vision model when it reads a scanned page: one fixed line, so a test can see the page was 'read'."""
    return "Fake reading of a scanned page. The printer on floor 4 is called PRN-04."


def fake_stt(audio: bytes, fmt: str, seconds: float = 0.0) -> str:
    """A stand-in for the speech model: every recording 'says' the same question. The recording checks (silence, length, type) stay real."""
    return "how long can a v p n session stay connected"


def fake_embed(texts: list[str]) -> list[list[float]]:
    """A stand-in for the embedding model: a tiny vector from the text, only so an index can be rebuilt without Ollama."""
    return [[float(len(t) % 7 + 1), float(sum(map(ord, t[:20])) % 11 + 1), 1.0] for t in texts]


def fake_draw(prompt: str) -> bytes:
    """A stand-in for the picture model: a small plain picture, so a test can see the button, the picture and its label without a model."""
    import io
    from PIL import Image
    out = io.BytesIO()
    Image.new("RGB", (64, 64), (120, 170, 200)).save(out, "PNG")
    return out.getvalue()
