"""The language guess and the fixed sentences in other languages. Plain code, no model."""
import csv

import pytest

from app.config import DECLINE_SENTENCE, REFUSAL_SENTENCE
from app.eval_suite import load_suite
from app.language import TRANSLATED, detect_language, is_english, localise, localise_result
from tests.lang_data import QUESTIONS, UNSAFE


def test_every_english_question_the_project_has_is_english():
    """No false alarms: a wrong 'not English' would add a model call and a translation to a question that did not need either."""
    texts = [c["input"] for c in load_suite()] + [t for c in load_suite() for t in c["turns"]]
    with open("data/retrieval_test_set.csv", encoding="utf-8", newline="") as f:
        texts += [r["question"] for r in csv.DictReader(f)] + [r["previous_question"] for r in csv.DictReader(open("data/retrieval_test_set.csv", encoding="utf-8", newline=""))]
    with open("data/test_questions.csv", encoding="utf-8", newline="") as f:
        texts += [r["question"] for r in csv.DictReader(f)]
    texts = [t for t in texts if t.strip() and not t.startswith(("Ignorez vos", "¿Cuánto tiempo puede"))]  # the suite's own French and Spanish cases
    wrong = [(t[:60], detect_language(t)) for t in texts if detect_language(t) != "en"]
    assert len(texts) > 100 and wrong == []


@pytest.mark.parametrize("language,question", [(lang, q) for lang, qs in QUESTIONS.items() for q in qs])
def test_questions_in_other_languages_are_recognised(language, question):
    assert detect_language(question) == language


@pytest.mark.parametrize("text", ["VPN-806?", "ok", "MFA", "WIFI-117 NorthLink", "hello", "", "   ", "12345", "!!!", "How do I install the VPN on a Mac?"])
def test_short_or_unclear_text_counts_as_english(text):
    assert detect_language(text) == "en" and is_english(text)


@pytest.mark.parametrize("text", ["如何设置新手机上的多因素认证？", "كيف أقوم بإعداد المصادقة على هاتف جديد؟", "Как настроить MFA на новом телефоне?"])
def test_another_script_is_other(text):
    assert detect_language(text) == "other"


def test_a_name_inside_an_otherwise_english_sentence_stays_english():
    assert detect_language("My Müller account is locked, what can I do?") == "en"
    assert detect_language("Is the café wifi covered by the VPN policy?") == "en"


@pytest.mark.parametrize("question", [q for qs in UNSAFE.values() for q in qs])
def test_the_unsafe_requests_are_also_recognised_as_not_english(question):
    assert not is_english(question)


def test_the_translated_sentences_keep_the_contact_details_and_exist_for_three_languages():
    assert set(TRANSLATED) == {"es", "fr", "de"}
    for language, sentences in TRANSLATED.items():
        for kind in ("decline", "refusal"):
            assert "4357" in sentences[kind] and "servicedesk@northwind.example" in sentences[kind]
            assert sentences[kind] != (DECLINE_SENTENCE if kind == "decline" else REFUSAL_SENTENCE)


def test_a_decline_or_refusal_is_shown_in_the_question_language_and_the_english_is_kept():
    declined = localise_result({"answer": DECLINE_SENTENCE, "declined": True, "refused": False}, "es")
    assert declined["answer"] == TRANSLATED["es"]["decline"] and declined["answer_en"] == DECLINE_SENTENCE and declined["language"] == "es"
    refused = localise_result({"answer": REFUSAL_SENTENCE, "declined": False, "refused": True}, "de")
    assert refused["answer"] == TRANSLATED["de"]["refusal"] and refused["answer_en"] == REFUSAL_SENTENCE


def test_a_real_answer_and_a_language_without_a_translation_are_left_alone():
    answered = localise_result({"answer": "Respuesta [1].", "declined": False, "refused": False}, "es")
    assert answered["answer"] == "Respuesta [1]." and "answer_en" not in answered and answered["language"] == "es"
    portuguese = localise_result({"answer": DECLINE_SENTENCE, "declined": True, "refused": False}, "pt")
    assert portuguese["answer"] == DECLINE_SENTENCE and localise("decline", "pt") is None
