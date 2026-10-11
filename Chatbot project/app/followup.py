"""Does a question only make sense with the one before it? ("And for P3?", "Is that the same for contractors?")

A cheap check in plain code, so the chatbot spends a model call on rewriting only when it is needed.
"""
import re

CONNECTORS = ("and", "also", "but", "so", "then", "what about", "how about", "what if", "is that", "does that", "is it",
              "does it", "same for", "why", "which one", "what else")
PRONOUNS = frozenset({"it", "its", "that", "this", "they", "them", "those", "these", "there"})
MAX_WORDS = 12  # a long question usually says what it is about


def looks_like_follow_up(question: str) -> bool:
    """True for a short question that starts with a connector ("And ...", "What about ...") or leans on a pronoun ("... after that?")."""
    words = re.findall(r"[a-z0-9']+", question.lower())
    if not words or len(words) > MAX_WORDS:
        return False
    text = " ".join(words)
    starts_with_connector = any(text == c or text.startswith(c + " ") for c in CONNECTORS)
    return starts_with_connector or any(w in PRONOUNS for w in words)
