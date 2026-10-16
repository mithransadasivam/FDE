"""Tells you when Activity 1 is done: all five tests pass. No model is used."""

from app.answer_checks import check_citations

DECLINE = "I don't know: the documents don't cover that."


def test_a_correctly_cited_answer_has_no_problems():
    assert (
        check_citations("Sessions last 12 hours [1]. MFA is required [2].", 2, False)
        == []
    )


def test_an_answer_without_citations_is_a_problem():
    assert check_citations("Sessions last 12 hours.", 2, False) == ["no citations"]


def test_a_citation_to_a_missing_source_is_a_problem_once():
    assert check_citations("A [1]. B [3]. C [3].", 2, False) == [
        "cites [3] but there are only 2 sources"
    ]


def test_a_declined_answer_must_not_cite_anything():
    assert check_citations(DECLINE, 0, True) == []
    assert check_citations(DECLINE + " [1]", 1, True) == [
        "declined answer contains citations"
    ]


def test_citation_zero_is_out_of_range():
    assert check_citations("Logs are kept for 1 year [0].", 1, False) == [
        "cites [0] but there are only 1 sources"
    ]
