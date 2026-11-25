"""Ticket ENG-1103: the cascade. The weakest field decides whether a document needs the pilot."""

from app.distil import service
from app.distil.cascade import route_document
from app.distil.reader import SmallField
from app.prototype.models import FIELDS
from tests.distilkit import trained


def fields(**conf):
    out = []
    for f in FIELDS:
        c = conf.get(f, 0.97)
        out.append(SmallField(name=f, label=f, value="" if c is None else "v", word_ids=[] if c is None else ["w1"], confidence=0.0 if c is None else c))
    return out


def test_a_document_sure_on_every_field_stays_with_the_small_model():
    d = route_document(fields(), 0.7)
    assert d.route == "small" and d.reasons == []


def test_one_unsure_field_sends_the_document_to_the_teacher():
    d = route_document(fields(statement_date=0.59), 0.7)
    assert d.route == "teacher" and d.reasons == ["statement_date 0.59 below 0.70"]


def test_the_average_does_not_hide_a_weak_field():
    d = route_document(fields(full_name=0.99, address=0.99, statement_date=0.52, issuer=0.99), 0.8)  # average 0.87
    assert d.route == "teacher"


def test_a_missing_field_says_missing():
    d = route_document(fields(statement_date=None), 0.7)
    assert d.route == "teacher" and d.reasons == ["statement_date missing"]


def test_every_reason_is_listed_in_field_order():
    d = route_document(fields(full_name=0.41, statement_date=None, issuer=0.6), 0.7)
    assert d.reasons == ["full_name 0.41 below 0.70", "statement_date missing", "issuer 0.60 below 0.70"]


def test_exactly_at_the_threshold_is_sure_enough():
    assert route_document(fields(address=0.7), 0.7).route == "small"


def test_a_confidence_just_below_is_shown_rounded_down():
    assert route_document(fields(full_name=0.699), 0.7).reasons == ["full_name 0.69 below 0.70"]


def test_the_cascade_lets_no_more_errors_through_than_the_pilot():
    """October at 0.70 (after ENG-1101 and ENG-1102): no small-model error slips through, and in all no more than the pilot's 3."""
    c = service.cascade(trained(), "october", 0.7, save=False)
    assert c["slipped_small"] == 0
    assert c["slipped"] <= c["pilot"]["slipped"] == 3
    assert c["teacher_share"] < 0.35
