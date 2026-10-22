"""Day 17: find and hide personal data with Microsoft Presidio.

Presidio has two parts. The analyzer finds personal data: it combines a language model (spaCy's
en_core_web_sm, which spots names and places), patterns (regular expressions, such as an email
address) and checks (a card number must pass the Luhn check). Each finding has a type, a position
and a score between 0 and 1. The anonymizer then replaces each finding, here with its type:
"+44 7700 900211" becomes "<UK_MOBILE>".

Done: build_analyzer(), with two recognisers of our own for what Presidio misses.
Activity 3: fill in redact(). Check it with tests/test_pii.py.
"""

import logging
from functools import lru_cache

import tldextract

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine

# Presidio's email check looks up web domain names online; without a connection it uses its own copy
logging.getLogger("tldextract").setLevel(logging.CRITICAL)
tldextract.tldextract.TLD_EXTRACTOR = tldextract.TLDExtract(suffix_list_urls=())  # never go online

SPACY_MODEL = "en_core_web_sm"  # small (about 15 MB); en_core_web_lg finds names better
# What we hide. Names, dates and places are left alone on purpose: an IT answer often names a
# colleague or a date, and hiding those would make good answers useless.
PII_ENTITIES = [
    "PHONE_NUMBER",
    "UK_MOBILE",
    "EMAIL_ADDRESS",
    "CREDIT_CARD",
    "IBAN_CODE",
    "HOME_ADDRESS",
]
MIN_SCORE = 0.4  # findings scored lower than this are ignored

# Presidio's phone check missed "+44 7700 900211" in our tests, so we add a pattern of our own
UK_MOBILE = PatternRecognizer(
    supported_entity="UK_MOBILE",
    patterns=[
        Pattern("UK mobile", r"(?:\+44\s?7\d{3}|\b07\d{3})\s?\d{3}\s?\d{3}\b", 0.6)
    ],
    context=["mobile", "phone", "call", "text"],
)
# A house number and a street: "2 Larch Close", "15 Mill Lane"
HOME_ADDRESS = PatternRecognizer(
    supported_entity="HOME_ADDRESS",
    patterns=[
        Pattern(
            "street address",
            r"\b\d{1,4}[A-Za-z]?\s+(?:[A-Z][a-z]+\s+){1,3}"
            r"(?:Road|Street|Lane|Close|Avenue|Way|Drive|Court|Gardens|Place|Crescent|Grove|Row|Terrace)\b"
            r"(?:,\s*[A-Z][a-z]+)?",
            0.6,
        )
    ],
    context=["home", "address", "lives"],
)


@lru_cache(maxsize=1)
def build_analyzer() -> AnalyzerEngine:
    """Presidio's analyzer with the small spaCy model and our two extra recognisers. Loading the
    model takes a few seconds, so it is built once and reused."""
    nlp = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": SPACY_MODEL}],
        }
    ).create_engine()
    analyzer = AnalyzerEngine(nlp_engine=nlp, supported_languages=["en"])
    analyzer.registry.add_recognizer(UK_MOBILE)
    analyzer.registry.add_recognizer(HOME_ADDRESS)
    return analyzer


def redact(text: str, analyzer: AnalyzerEngine | None = None) -> dict:
    """TODO (Activity 3): hide the personal data in a text.

    Rules (tests/test_pii.py checks each one):
    - analyzer defaults to build_analyzer()
    - findings = analyzer.analyze(text=text, language="en", entities=PII_ENTITIES,
                                  score_threshold=MIN_SCORE)
    - no findings: return {"text": text, "found": []}
    - otherwise: hidden = AnonymizerEngine().anonymize(text=text, analyzer_results=findings)
      (its default replaces each finding with its type in angle brackets, like <EMAIL_ADDRESS>)
    - return {"text": hidden.text,
              "found": the entity types of the findings, ordered by where they start in the text}
      Only the types: the found list goes into logs, so it must not contain the data itself.
    """
    analyzer = analyzer or build_analyzer()
    findings = analyzer.analyze(
        text=text, language="en", entities=PII_ENTITIES, score_threshold=MIN_SCORE
    )
    if not findings:
        return {"text": text, "found": []}
    hidden = AnonymizerEngine().anonymize(text=text, analyzer_results=findings)
    ordered = sorted(findings, key=lambda f: f.start)
    return {"text": hidden.text, "found": [f.entity_type for f in ordered]}
