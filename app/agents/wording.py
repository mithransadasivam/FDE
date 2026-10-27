"""Biased-wording check: rules in code, not a model (Prompt 8).
Rules are fast, free, explainable and the same every time. Each rule is a pattern, a reason and a neutral suggestion."""
import re

from app.schemas import WordingFlag

RULES: list[tuple[str, str, str]] = [
    (r"\byoung and energetic\b", "Suggests an age preference, which can be age discrimination.",
     "motivated and able to work on our on-call rota"),
    (r"\b(?:young|youthful)\b", "Suggests an age preference, which can be age discrimination.", "motivated"),
    (r"\benergetic\b", "Often used as a coded age preference; describe the actual demands of the job instead.",
     "able to work at a steady pace in a busy team"),
    (r"\bnative(?: english)? speakers?\b", "Excludes people by national origin or first language. Ask for the level you need.",
     "fluent written and spoken English"),
    (r"\b(?:rock\s?stars?|ninjas?|gurus?|wizards?)\b", "Informal, gendered and off-putting; it describes a personality, not a skill.",
     "an experienced, skilled professional"),
    (r"\b(?:recent|fresh) (?:graduates?|grads?)\b", "Suggests an age preference. Say what experience or qualification you need.",
     "someone starting their career, or an experienced professional"),
    (r"\bdigital natives?\b", "Suggests an age preference. Say which digital skills the job needs.",
     "confident with modern digital tools"),
    (r"\b(?:he|she) will\b", "Assumes the gender of the person hired.", "they will"),
    (r"\bhe/she\b|\bhis or her\b|\bhis/her\b", "Assumes a binary gender; use neutral wording.", "they / their"),
    (r"\bmanpower\b", "Gendered word for staff.", "workforce / staffing"),
    (r"\b(?:salesman|chairman|foreman|policeman)\b", "Gendered job word.", "salesperson / chair / supervisor / police officer"),
    (r"\bguys\b", "Gendered way to address a mixed group.", "team / everyone"),
    (r"\bculture fit\b", "Vague, and can favour people similar to the current team.", "shares our values and ways of working"),
    (r"\bmature (?:person|candidate|individual|professional)\b", "Suggests an age preference.", "experienced professional"),
]
COMPILED = [(re.compile(p, re.I), reason, suggestion) for p, reason, suggestion in RULES]


def check_wording(text: str, where: str = "voice note") -> list[WordingFlag]:
    """Report each phrase once, longest match first: a match inside one already found is skipped."""
    found: list[tuple[int, int, str, str, str]] = []
    for rx, reason, suggestion in COMPILED:
        for m in rx.finditer(text):
            found.append((m.start(), m.end(), m.group(0), reason, suggestion))
    found.sort(key=lambda f: (-(f[1] - f[0]), f[0]))
    taken: list[tuple[int, int]] = []
    seen_phrases: set[str] = set()
    kept = []
    for start, end, phrase, reason, suggestion in found:
        if any(start < b and a < end for a, b in taken):
            continue
        taken.append((start, end))
        if phrase.lower() in seen_phrases:
            continue
        seen_phrases.add(phrase.lower())
        kept.append((start, WordingFlag(phrase=phrase, reason=reason, suggestion=suggestion, where=where)))
    return [f for _, f in sorted(kept, key=lambda k: k[0])]


def check_requisition(transcript: str | None, job_text: str | None) -> list[WordingFlag]:
    """Flags for the voice note and for the generated job text, stored on the requisition."""
    flags = check_wording(transcript or "", "voice note")
    if job_text:
        flags += check_wording(job_text, "job text")
    return flags
