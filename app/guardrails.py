"""Guardrails: input and output checks that do not depend on a prompt (Day 17 patterns, rules 4, 7, 8 and 9)."""
import re

# ---- rule 8: text from candidates is data, never an instruction -----------------------------------------------------------
INJECTION_PATTERNS = [
    r"ignore\s+(?:all\s+|any\s+|your\s+|the\s+)*(?:previous\s+|prior\s+|above\s+)*(?:instructions|rules|guidelines)",
    r"note\s+to\s+ai", r"\bai\s*:\s", r"system\s*:\s", r"admin\s+mode", r"you\s+are\s+now\b", r"disregard\b.*\b(?:instructions|rules)",
    r"rank\s+(?:them|this\s+candidate|me|him|her)\s+first", r"\bbest\s+match\b.*\brank", r"strong\s+hire", r"shortlist\s+me",
    r"give\s+(?:me\s+)?(?:a\s+|every\s+skill\s+a\s+)?(?:score\s+of\s+)?3\b", r"mark\s+all\b.*\b3", r"score\s+(?:for\s+this\s+candidate\s+)?to\s+3",
    r"move\s+me\s+to\b", r"skip\s+the\s+rest\b.*\bpass", r"pass\s+me\b", r"send\s+an?\s+.{0,30}\bemail\b",
    r"(?:reveal|print|show)\s+.{0,30}(?:system\s+prompt|instructions)",
]
INJECTION_RX = [re.compile(p, re.I) for p in INJECTION_PATTERNS]


def scan_injection(text: str) -> list[str]:
    """The pieces of text that look like instructions to an AI. They are flagged and ignored, never followed."""
    hits = []
    for line in re.split(r"[\n.;]", text or ""):
        if any(rx.search(line) for rx in INJECTION_RX):
            hits.append(line.strip())
    return [h for h in hits if h]


def strip_injection(text: str) -> str:
    """The text with every line that looks like an instruction removed (used before a model reads candidate text)."""
    out = []
    for line in (text or "").splitlines():
        out.append(line if not any(rx.search(line) for rx in INJECTION_RX) else "")
    return "\n".join(out)


# ---- rules 3 and 4: protected traits must never reach a scoring prompt ------------------------------------------------------
EMAIL_RX = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RX = re.compile(r"\+?\d[\d ()-]{7,}\d")
DOB_RX = re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b")
TRAIT_RX = [
    ("gender", re.compile(r"\b(?:she|he|her|his|hers|him|woman|women|man|men|female|male|mrs|mr|ms|miss|girl|boy)\b", re.I)),
    ("age", re.compile(r"\b(?:date of birth|born in|years old|aged \d+|age \d+|over \d+ years since|graduated (?:in )?(?:19|20)\d\d)\b", re.I)),
    ("family", re.compile(r"\b(?:pregnan\w*|maternity|married|marital|children|kids|family plans|husband|wife)\b", re.I)),
    ("religion", re.compile(r"\b(?:muslim|christian|jewish|hindu|sikh|buddhist|church|mosque|temple|religio\w*)\b", re.I)),
    ("health", re.compile(r"\b(?:disabled|disability|illness|diagnos\w*|chronic|mental health|wheelchair)\b", re.I)),
    ("union_politics", re.compile(r"\b(?:trade union|union member\w*|political party|voted)\b", re.I)),
    ("nationality", re.compile(r"\b(?:nationality|citizen of|ethnic\w*|immigrant|native speaker)\b", re.I)),
]


def scan_protected(text: str, identity_strings: list[str] | None = None) -> list[tuple[str, str]]:
    """(kind, snippet) for every identity detail or protected trait in the text. Used on every scoring prompt."""
    hits: list[tuple[str, str]] = []
    for s in identity_strings or []:
        if len(s) >= 3 and re.search(r"(?<![\w])" + re.escape(s) + r"(?![\w])", text, re.I):
            hits.append(("identity", s))
    for kind, rx in (("email", EMAIL_RX), ("phone", PHONE_RX), ("date_of_birth", DOB_RX)):
        hits += [(kind, m.group(0)) for m in rx.finditer(text)]
    for kind, rx in TRAIT_RX:
        hits += [(kind, m.group(0)) for m in rx.finditer(text)]
    return hits


def mask_protected(text: str) -> str:
    """Removes protected disclosures from what a candidate said before it is scored (for example a mention of pregnancy)."""
    out = text or ""
    for _, rx in TRAIT_RX:
        out = rx.sub("[removed]", out)
    out = EMAIL_RX.sub("[removed]", out)
    return PHONE_RX.sub("[removed]", out)


# ---- rule 7: questions that must not be asked --------------------------------------------------------------------------------
FORBIDDEN = {
    "age": r"\bhow old\b|\byour age\b|\bwhat year were you born\b|\bdate of birth\b|\bwhen were you born\b|\bplan to retire\b|\btoo old\b|\btoo young\b",
    "family or pregnancy": r"\bdo you have (?:any )?(?:kids|children)\b|\b(?:any )?(?:kids|children)\b.*\?|\bmarried\b|\bmarital\b|\bhusband\b|\bwife\b|\bpregnan\w*|\bfamily plans\b|\bstart a family\b|\bboyfriend\b|\bgirlfriend\b",
    "religion": r"\breligio\w*|\bchurch\b|\bmosque\b|\bwhich god\b|\bwhat faith\b|\byour beliefs?\b",
    "health or disability": r"\bdisab\w*|\bhealth condition\b|\bmedical\b|\billness\b|\bmental health\b|\bdiagnos\w*|\bmedication\b",
    "nationality or origin": r"\bwhere are you (?:really )?from\b|\bnationality\b|\bcitizen\w*\b|\bethnic\w*\b|\bmother tongue\b|\bwhere were you born\b|\bnative language\b",
    "sexual orientation or gender identity": r"\bsexual\w*|\bgay\b|\blesbian\b|\bgender identity\b|\btransgender\b",
    "political views or union membership": r"\bpolitic\w*|\bwho did you vote\b|\btrade union\b|\bunion member\w*|\bjoin a union\b",
}
FORBIDDEN_RX = {k: re.compile(v, re.I) for k, v in FORBIDDEN.items()}


def forbidden_question(text: str) -> list[tuple[str, str]]:
    """(category, matched words) for a question that must not be asked. Empty if the question is fine."""
    return [(cat, m.group(0)) for cat, rx in FORBIDDEN_RX.items() for m in [rx.search(text or "")] if m]


FORBIDDEN_MESSAGE = ("Question not allowed: {category} must not be asked or used. Move on, and if you need to check on-call "
                     "availability, ask everyone the same neutral question about the rota.")


# ---- rule 9: what the recruiter assistant may be asked -----------------------------------------------------------------------
PRIVATE_REQUEST_RX = re.compile(
    r"date of birth|\bdob\b|birthday|phone|e-?mail|salary|address|contact (?:details|info)|home\b|passport|"
    r"system (?:prompt|instructions)|your (?:instructions|rules|prompt)|ignore your (?:rules|instructions)|previous instructions", re.I)
PROTECTED_INFERENCE_RX = re.compile(r"\b(?:youngest|oldest|how old|age of|which (?:gender|sex)|is (?:he|she) (?:a )?(?:man|woman)|religion|nationality|"
                                    r"pregnan\w*|married|disabled|ethnic\w*)\b", re.I)


def assistant_request_check(question: str) -> tuple[bool, str]:
    """(allowed, reason). Private columns, the assistant's own instructions and protected traits are refused by code."""
    if PRIVATE_REQUEST_RX.search(question or ""):
        return False, ("I can't share private details (contact details, date of birth, salary, addresses) or my own instructions. "
                       "I can answer questions about skills, experience, stages and the hiring policy.")
    if PROTECTED_INFERENCE_RX.search(question or ""):
        return False, "I can't compare or rank people by age, gender, religion, nationality, family status or health. Ask about skills and experience instead."
    return True, ""
