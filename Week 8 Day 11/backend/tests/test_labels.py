"""Ticket ENG-1101: training labels from the teacher's reads, keeping only the reads the teacher is sure of."""

from app.distil.labels import word_labels
from app.distil.model import training_rows
from app.distil.reads import load
from tests.distilkit import read


def test_every_cited_word_gets_its_field_and_the_rest_get_O():
    labels = word_labels(read())
    assert labels == ["issuer", "issuer", "full_name", "full_name", "full_name", "address", "address", "address", "address", "address",
                      "O", "O", "statement_date", "statement_date", "statement_date"]


def test_a_read_the_two_readings_disagree_on_is_left_out():
    r = read()
    r["vision"]["statement_date"] = "31 Oct 2026"  # the vision reading saw another date
    assert word_labels(r) is None


def test_any_field_can_leave_a_read_out():
    for f in ("full_name", "address", "issuer"):
        r = read()
        r["vision"][f] = "something else"
        assert word_labels(r) is None, f


def test_values_are_compared_ignoring_case_spaces_and_punctuation():
    r = read()
    r["vision"]["address"] = "3 Spa Road, GL5 1AB"
    r["vision"]["full_name"] = "MR ALI KHAN"
    assert word_labels(r) is not None


def test_a_field_with_no_cited_words_leaves_the_read_out():
    r = read()
    r["parser"]["issuer"]["word_ids"] = []
    assert word_labels(r) is None


def test_the_pilot_reads_keep_the_ones_the_teacher_is_sure_of():
    rows = training_rows(load("pilot"))
    assert len(rows["kept"]) == 1153 and len(rows["skipped"]) == 347


def test_the_teachers_statement_period_mistakes_are_left_out():
    """The teacher sometimes cites the statement period's end ("... to 31 Aug 2026"). Most of those reads are left out."""
    kept = set(training_rows(load("pilot"))["kept"])
    period_end = [r for r in load("pilot") if r["kind"] == "bank_statement" and r["parser"]["statement_date"]["word_ids"]
                  and _before(r, r["parser"]["statement_date"]["word_ids"][0]) == "to"]
    assert len(period_end) > 100
    assert sum(r["doc_id"] in kept for r in period_end) <= 0.15 * len(period_end)


def _before(r, wid):
    ids = [w[0] for w in r["words"]]
    i = ids.index(wid)
    return r["words"][i - 1][1] if i else ""
