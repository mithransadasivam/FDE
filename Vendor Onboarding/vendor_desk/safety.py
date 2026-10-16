"""Two defences used everywhere text crosses a boundary.

redact(): removes bank account numbers and sort codes (policy §10.1) from any text before it reaches a model,
a log or the audit trail. scan_injection(): spots text that tries to give the system orders (policy §1.2).
The scanner only flags. It never changes a decision by itself and never obeys the text.
"""
import re

_ACCOUNT_LINE = re.compile(r"(?im)^(\s*(?:account number|sort code|iban)\s*:\s*).*$")
_LONG_DIGITS = re.compile(r"\b\d{8,12}\b")
_SORT_CODE = re.compile(r"\b\d{2}-\d{2}-\d{2}\b")
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}\b")

REDACTED = "[REDACTED]"


def redact(text: str) -> str:
    text = _ACCOUNT_LINE.sub(lambda m: m.group(1) + REDACTED, text)
    text = _IBAN.sub(REDACTED, text)
    text = _SORT_CODE.sub(REDACTED, text)
    return _LONG_DIGITS.sub(REDACTED, text)


def redact_obj(value):
    """Redact every string inside a nested dict/list."""
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, dict):
        return {k: redact_obj(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_obj(v) for v in value]
    return value


_INJECTION_PATTERNS = [
    ("ignore_instructions", r"\b(ignore|disregard|forget|override)\b.{0,40}\b(instructions?|policy|rules?|checks?|guidelines)\b"),
    ("skip_checks", r"\b(skip|bypass|disable|waive)\b.{0,30}\b(all |the |any )?(checks?|screening|verification|policy|review)\b"),
    ("approve_now", r"\b(approve|approved)\b.{0,25}\b(this|the|that)\b.{0,12}\b(vendor|case|request|supplier)\b|\bmark\b.{0,30}\b(approved|passed|verified|ready for approval)\b"),
    ("self_approval", r"\b(i|we) (have )?(already )?(reviewed|approve|approved)\b.{0,60}\b(myself|this vendor)\b"),
    ("create_without_approval", r"\bcreate the vendor( record)?\b.{0,30}\b(straight away|immediately|now)\b"),
    ("addressed_to_ai", r"\b(note to|message to|instruction for)\b.{0,12}\b(ai|assistant|system|model|agent)\b"),
    ("role_markers", r"(?i)(^|\n)\s*(system|assistant)\s*(note|prompt|message)?\s*:"),
    ("system_note", r"\bsystem note\b"),
    ("mark_all_passed", r"\bmark (every|all) (check|document)s?\b"),
]
_COMPILED = [(name, re.compile(p, re.I | re.S)) for name, p in _INJECTION_PATTERNS]


def scan_injection(text: str) -> list[str]:
    """Names of the injection patterns found in text (empty list when it looks normal)."""
    return sorted({name for name, rx in _COMPILED if rx.search(text)})
