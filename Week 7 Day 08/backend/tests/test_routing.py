"""Ticket ENG-602: route_field(). Run: python -m pytest -q tests/test_routing.py"""

from app.pipeline.routing import route_field
from app.prototype.models import Field


def f(value="30 Sep 2026", confidence=0.97, status="ok", note=""):
    return Field(name="statement_date", label="Statement date", value=value, confidence=confidence, status=status, note=note)


def test_a_sure_field_that_both_methods_agree_on_goes_straight_through():
    r = route_field(f(), f())
    assert r.decision == "auto" and r.reasons == []


def test_low_confidence_goes_to_a_person():
    r = route_field(f(confidence=0.62, status="check"), f())
    assert r.decision == "review"
    assert r.reasons == ["OCR confidence 0.62 is below 0.85"]


def test_the_threshold_is_a_parameter():
    assert route_field(f(confidence=0.88), None, ok_at=0.85).decision == "auto"
    r = route_field(f(confidence=0.88), None, ok_at=0.9)
    assert r.reasons == ["OCR confidence 0.88 is below 0.90"]


def test_a_missing_field_gives_its_note():
    r = route_field(f(value="", confidence=0.0, status="missing", note="Not found on the page"), f())
    assert r.decision == "review" and r.reasons[0] == "Not found on the page"


def test_a_value_not_on_the_page_gives_its_note_or_a_default():
    r = route_field(f(confidence=0.0, status="not_on_page", note='The page says "29 Sep 2026"'), f())
    assert r.reasons[0] == 'The page says "29 Sep 2026"'
    r = route_field(f(confidence=0.0, status="not_on_page", note=""), f())
    assert r.reasons[0] == "Not found on the page"


def test_disagreement_goes_to_a_person_even_with_perfect_confidence():
    r = route_field(f("30 Sep 2026", 1.0), f("03 Oct 2026"))
    assert r.decision == "review"
    assert r.reasons == ['The vision model read "03 Oct 2026"']


def test_a_vision_model_with_no_value_counts_as_disagreeing():
    r = route_field(f(), f(value="", confidence=0.0, status="missing"))
    assert r.reasons == ["The vision model found no value"]


def test_agreement_compares_letters_and_digits_only():
    assert route_field(f("Flat 3, 14 Larkspur Row"), f("Flat 3 14 Larkspur Row")).decision == "auto"
    assert route_field(f("30 Sep 2026"), f("30 SEP 2026")).decision == "auto"


def test_agreement_can_be_switched_off_or_left_out():
    assert route_field(f("30 Sep 2026"), f("03 Oct 2026"), use_agreement=False).decision == "auto"
    assert route_field(f("30 Sep 2026"), None).decision == "auto"


def test_both_reasons_are_given_in_order():
    r = route_field(f("01 Sep 2026", 0.58, "doubtful"), f("04 Sep 2026"))
    assert r.reasons == ["OCR confidence 0.58 is below 0.85", 'The vision model read "04 Sep 2026"']


def test_a_field_a_person_confirmed_is_never_sent_again():
    r = route_field(f(status="confirmed", confidence=0.4), f("other"))
    assert r.decision == "auto" and r.reasons == []


def test_on_the_october_batch_agreement_catches_what_confidence_misses():
    from app.pipeline import service as S

    S.run("october", ["extract_v2", "extract_vlm_v1"], 8)
    alone = S.routing("october", "extract_v2", "extract_vlm_v1", 0.85, False)
    both = S.routing("october", "extract_v2", "extract_vlm_v1", 0.85, True)
    assert (alone["review"], alone["slipped"]) == (54, 20)
    assert (both["review"], both["slipped"]) == (87, 3)
    assert both["accuracy_after_review"] > S.human_bar("october")["one_keyer"] > alone["accuracy_after_review"]
