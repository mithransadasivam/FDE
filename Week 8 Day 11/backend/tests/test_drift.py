"""Homework Task 1: which kinds of document should the small model be retrained for?"""

from app.distil.drift import retrain_candidates


def row(i, kind, route="small", reasons=None):
    return {"doc_id": f"{kind[:1]}-{i}", "kind": kind, "route": route, "reasons": reasons or []}


def test_one_entry_per_kind_sorted_by_name():
    rows = [row(1, "utility_bill"), row(2, "bank_statement"), row(3, "council_tax")]
    assert [k["kind"] for k in retrain_candidates(rows)] == ["bank_statement", "council_tax", "utility_bill"]


def test_share_and_counts():
    rows = [row(i, "council_tax", "teacher", ["statement_date missing"]) for i in range(9)] + [row(9, "council_tax")]
    k = retrain_candidates(rows)[0]
    assert (k["documents"], k["to_teacher"], k["share"]) == (10, 9, 0.9)


def test_top_reason_is_the_field_named_most():
    rows = [row(1, "council_tax", "teacher", ["statement_date missing"]), row(2, "council_tax", "teacher", ["statement_date 0.40 below 0.70", "address 0.6 below 0.70"]),
            row(3, "council_tax", "teacher", ["address 0.65 below 0.70"]), row(4, "council_tax", "teacher", ["statement_date missing"])]
    assert retrain_candidates(rows)[0]["top_reason"] == "statement_date"
    assert retrain_candidates([row(1, "utility_bill")])[0]["top_reason"] is None


def test_retrain_needs_a_high_share_and_enough_documents():
    many = [row(i, "council_tax", "teacher", ["statement_date missing"]) for i in range(12)]
    few = [row(i, "council_tax", "teacher", ["statement_date missing"]) for i in range(5)]
    half = [row(i, "utility_bill", "teacher" if i < 6 else "small", ["issuer missing"] if i < 6 else []) for i in range(12)]
    assert retrain_candidates(many)[0]["retrain"] is True
    assert retrain_candidates(few)[0]["retrain"] is False
    assert retrain_candidates(half)[0]["retrain"] is False  # 0.5 is not above 0.5
    assert retrain_candidates(few, min_docs=5)[0]["retrain"] is True


def test_spot_checks_are_not_a_reason_to_retrain():
    rows = [row(i, "bank_statement", "teacher", ["spot check"]) for i in range(11)]
    k = retrain_candidates(rows)[0]
    assert (k["to_teacher"], k["share"], k["retrain"], k["top_reason"]) == (0, 0.0, False, None)
