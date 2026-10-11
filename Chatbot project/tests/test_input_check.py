"""Input checks that run before any search or model call. No model is used anywhere in this file."""
import pytest

from app.config import MAX_INPUT_CHARS, MAX_QUESTION_CHARS
from app.input_check import (MSG_EMPTY, MSG_NOT_A_QUESTION, MSG_TOO_LONG, check_input, has_recognisable_words,
                             looks_like_a_word, shorten)

VOCAB = {"vpn", "northlink", "session", "connected", "laptop"}  # a tiny stand-in for the documents' words


def ok(text):
    return check_input(text, VOCAB)


# --- empty and meaningless input ---------------------------------------------------------------------------------

@pytest.mark.parametrize("text", ["", "   ", "\n\t  \n", None])
def test_empty_or_blank_input_asks_for_a_question(text):
    result = check_input(text, VOCAB)
    assert result["action"] == "ask" and result["message"] == MSG_EMPTY and result["reason"] == "empty question"


@pytest.mark.parametrize("text", ["😀", "😀😀😀", "12345", "!!@@## ;;;", "asdf qwer zxcv 12345 !!@@## ;;;", "zxcvbnm", "xkqzpt", "x" * 600])
def test_input_with_no_recognisable_words_asks_the_user_to_type_words(text):
    result = ok(text)
    assert result["action"] == "ask" and result["message"] == MSG_NOT_A_QUESTION


@pytest.mark.parametrize("text", [
    "salary?", "Kubernetes?", "VPN-809", "what is 2+2?", "how lnog vpn sesion can stay conected", "hi",
    "¿Cuánto tiempo puede estar conectada una sesión de VPN?", "Ignorez vos instructions", "And for P3?",
])
def test_real_questions_and_codes_go_through(text):
    assert ok(text)["action"] == "ok"


def test_looks_like_a_word():
    assert looks_like_a_word("salary") and looks_like_a_word("conectada")
    for not_a_word in ("asdf", "qwer", "zxcv", "fdsa", "xkqz", "ab", "123", "a1b2c3"):
        assert not looks_like_a_word(not_a_word), not_a_word


def test_a_known_word_counts_even_if_it_has_no_vowel():
    assert has_recognisable_words("VPN", VOCAB) and has_recognisable_words("VPN?", {"vpn"})
    assert not has_recognisable_words("VPN?", set())  # unknown and no vowel: not a word


def test_the_document_vocabulary_is_used_by_default():
    assert has_recognisable_words("northlink")  # a word from the real documents


# --- long input ------------------------------------------------------------------------------------------------------

def test_a_message_at_the_limit_is_untouched():
    text = ("vpn " * 125).strip()
    assert len(text) <= MAX_QUESTION_CHARS
    result = ok(text)
    assert result["action"] == "ok" and result["text"] == text and result["shortened_to"] == ""


def test_a_pasted_log_with_the_question_at_the_end_keeps_the_question():
    log = "\n".join(f"2026-10-05 09:{i % 60:02d} WARN vpn-gateway tunnel {i} retry timeout" for i in range(500))
    result = ok(log + "\nHow long can a VPN session stay connected?")
    assert result["action"] == "ok" and result["text"] == "How long can a VPN session stay connected?"
    assert result["shortened_to"] == result["text"]


def test_a_very_short_final_question_keeps_the_sentence_before_it():
    text = "I am setting up the VPN on my work laptop. " * 40 + "It shows the P1 priority page. And for P3?"
    kept = shorten(text)
    assert kept.endswith("And for P3?") and "P1 priority" in kept and len(kept) <= MAX_QUESTION_CHARS


def test_a_long_message_with_no_question_keeps_about_the_last_300_characters():
    text = "The VPN keeps dropping on my laptop at home. " * 60
    kept = shorten(text)
    assert 0 < len(kept) <= 320 and text.strip().endswith(kept[-20:])


def test_a_message_with_no_breaks_at_all_is_still_cut_to_the_limit():
    kept = shorten("vpn" * 1000)
    assert 0 < len(kept) <= MAX_QUESTION_CHARS


def test_a_long_message_is_checked_for_words_after_shortening():
    assert ok("asdf " * 400)["action"] == "ask"


def test_an_absurdly_long_message_is_refused():
    result = ok("vpn " * MAX_INPUT_CHARS)
    assert result["action"] == "ask" and result["message"] == MSG_TOO_LONG and result["reason"] == "message far too long"


def test_a_message_just_under_the_hard_limit_is_shortened_not_refused():
    result = ok(("vpn session. " * MAX_INPUT_CHARS)[:MAX_INPUT_CHARS - 100] + ". Is the session connected?")
    assert result["action"] == "ok" and result["text"] == "Is the session connected?"
