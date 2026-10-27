"""Evidence (rule 2): every score points to an exact quote, and CODE checks the quote really is in the source. No quote, no score."""
import re

from app.schemas import BlindCandidate


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def quote_exists(quote: str, source: str) -> bool:
    """True only if the quote is a non-empty, exact piece of the source text (ignoring case and spacing)."""
    q = norm(quote)
    return len(q) >= 2 and q in norm(source)


def blind_text(b: BlindCandidate) -> str:
    """The text a scoring step reads for a candidate: skills and experience only, one line per fact. This is the source
    that score quotes must come from; it contains no identity."""
    lines = []
    if b.current_title:
        lines.append(f"Current title: {b.current_title}")
    if b.years_experience is not None:
        lines.append(f"Experience: {b.years_experience:g} years")
    lines += [f"Job: {j}" for j in b.jobs]
    if b.skills:
        lines.append("Skills: " + ", ".join(b.skills))
    lines += [f"Certification: {c}" for c in b.certifications]
    if b.education:
        lines.append(f"Education: {b.education}")
    return "\n".join(lines)
