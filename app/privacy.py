"""Identity hiding (Prompt 12). Scoring only ever sees a BlindCandidate, never a Candidate (rule 3).

make_blind() builds the blind record from skills and experience, and replaces any name, e-mail, phone, address or
date of birth that shows up inside another field with [hidden]. identity_leaks() is the check (and the test helper)
that says whether anything identifying still got through.
"""
import json
import re

from app.models import Candidate
from app.schemas import BlindCandidate

HIDDEN = "[hidden]"
EMAIL_RX = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RX = re.compile(r"\+?\d[\d ()-]{7,}\d")
DOB_RX = re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b")


def _val(profile: dict, field: str):
    return ((profile or {}).get(field) or {}).get("value")


def identity_strings(profile: dict) -> list[str]:
    """Everything in the profile that identifies the person: the name and each part of it, e-mail, phone, address, date of birth."""
    out: list[str] = []
    name = _val(profile, "name")
    if name:
        out.append(name)
        out += [p for p in re.split(r"[\s,.-]+", name) if len(p) >= 2]
    for field in ("email", "phone", "date_of_birth"):
        v = _val(profile, field)
        if v:
            out.append(v)
    address = _val(profile, "address")
    if address:
        out.append(address)
        out += [p.strip() for p in address.split(",") if len(p.strip()) >= 3]
    seen, unique = set(), []
    for s in sorted({s.strip() for s in out if s and s.strip()}, key=len, reverse=True):  # longest first
        if s.lower() not in seen:
            seen.add(s.lower())
            unique.append(s)
    return unique


def _pattern(secret: str) -> re.Pattern:
    return re.compile(r"(?<![\w])" + re.escape(secret) + r"(?![\w])", re.I)


# Age and gender PROXIES that can sit inside an ordinary field (a graduation year, a pronoun, a women-only scholarship).
PROXY_RX = [re.compile(p, re.I) for p in (
    r"\s*\((?:graduated\s+)?(?:19|20)\d{2}\)", r"\bgraduated\s+(?:in\s+)?(?:19|20)\d{2}\b",
    r"\bwomen(?:'s)?\s+in\s+\w+(?:\s+(?:society|network|scholarship))?", r"\bmen(?:'s)?\s+in\s+\w+\b",
    r"\b(?:she|he|her|his|hers|him)\b", r"\bwomen\b", r"\bmentors\s+other\s+\w+")]

_presidio = None


def _presidio_scrub(text: str) -> str:
    """Second layer: Presidio finds e-mails, phone numbers and web links that the exact-match rules did not know about.
    Its name detector (PERSON) is NOT used: on CVs it wrongly hides tool and company names such as Grafana or Docker,
    which would lower a candidate's score for no reason. Names are hidden by exact match on the candidate's own details."""
    global _presidio
    try:
        if _presidio is None:
            from presidio_analyzer import AnalyzerEngine
            from presidio_analyzer.nlp_engine import NlpEngineProvider

            nlp = NlpEngineProvider(nlp_configuration={"nlp_engine_name": "spacy", "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}]}).create_engine()
            _presidio = AnalyzerEngine(nlp_engine=nlp, supported_languages=["en"])
        found = _presidio.analyze(text=text, language="en", entities=["EMAIL_ADDRESS", "PHONE_NUMBER", "URL"], score_threshold=0.6)
    except Exception:
        return text  # Presidio is a bonus layer: the rules above already hide everything we know about
    for r in sorted(found, key=lambda r: r.start, reverse=True):
        text = text[:r.start] + HIDDEN + text[r.end:]
    return text


def _scrub(text: str | None, secrets: list[str]) -> str | None:
    if text is None:
        return None
    for secret in secrets:
        text = _pattern(secret).sub(HIDDEN, text)
    text = EMAIL_RX.sub(HIDDEN, text)
    text = PHONE_RX.sub(HIDDEN, text)
    text = DOB_RX.sub(HIDDEN, text)
    for rx in PROXY_RX:
        text = rx.sub("", text)
    return _presidio_scrub(re.sub(r"\s{2,}", " ", text).strip())


def make_blind(candidate: Candidate) -> BlindCandidate:
    p = candidate.profile or {}
    secrets = identity_strings(p)

    def one(field):
        return _scrub(_val(p, field), secrets)

    def many(field):
        return [_scrub(x, secrets) for x in (_val(p, field) or [])]

    return BlindCandidate(candidate_id=candidate.id, current_title=one("current_title"), jobs=many("jobs"),
                          years_experience=_val(p, "years_experience"), skills=many("skills"),
                          certifications=many("certifications"), education=one("education"))


def identity_leaks(blind: BlindCandidate, candidate: Candidate) -> list[str]:
    """Anything identifying that is still in the blind record. An empty list means no leak."""
    text = json.dumps(blind.model_dump(), ensure_ascii=False)
    leaks = [s for s in identity_strings(candidate.profile or {}) if _pattern(s).search(text)]
    for rx in (EMAIL_RX, PHONE_RX, DOB_RX):
        leaks += [m.group(0) for m in rx.finditer(text)]
    return leaks
