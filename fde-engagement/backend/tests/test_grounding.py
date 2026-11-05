"""Ticket ENG-301: ground every field on the words of the page. 8 tests."""

from fastapi.testclient import TestClient

from app.main import app
from app.prototype.grounding import ground_fields
from app.prototype.models import ExtractionReply, OcrWord

WORDS = [
    OcrWord(id="w1", text="Ms", box=[0.10, 0.20, 0.13, 0.22], confidence=0.99),
    OcrWord(id="w2", text="Ananya", box=[0.14, 0.20, 0.22, 0.22], confidence=0.97),
    OcrWord(id="w3", text="Mehta", box=[0.23, 0.20, 0.30, 0.22], confidence=0.98),
    OcrWord(id="w4", text="09", box=[0.60, 0.18, 0.63, 0.21], confidence=0.62),
    OcrWord(id="w5", text="Sep", box=[0.64, 0.18, 0.68, 0.21], confidence=0.97),
    OcrWord(id="w6", text="2026", box=[0.69, 0.18, 0.75, 0.21], confidence=0.96),
    OcrWord(id="w7", text="Lumenvale", box=[0.14, 0.03, 0.30, 0.06], confidence=0.55),
    OcrWord(id="w8", text="Energy", box=[0.31, 0.03, 0.42, 0.06], confidence=0.99),
    OcrWord(id="w9", text="GL50", box=[0.10, 0.30, 0.15, 0.32], confidence=0.97),
]


def reply(**fields):
    return ExtractionReply(fields=[{"name": k, "value": v[0], "word_ids": v[1]} for k, v in fields.items()])


def by_name(fields):
    return {f.name: f for f in fields}


def test_four_fields_in_order_with_labels():
    out = ground_fields(reply(full_name=("Ms Ananya Mehta", ["w1", "w2", "w3"])), WORDS)
    assert [f.name for f in out] == ["full_name", "address", "statement_date", "issuer"]
    assert [f.label for f in out] == ["Full name", "Address", "Statement date", "Issuer"]


def test_confidence_is_the_weakest_word_and_sets_the_status():
    f = by_name(ground_fields(reply(full_name=("Ms Ananya Mehta", ["w1", "w2", "w3"]),
                                    statement_date=("09 Sep 2026", ["w4", "w5", "w6"]),
                                    issuer=("Lumenvale Energy", ["w7", "w8"])), WORDS))
    assert (f["full_name"].confidence, f["full_name"].status) == (0.97, "ok")
    assert (f["statement_date"].confidence, f["statement_date"].status) == (0.62, "check")
    assert (f["issuer"].confidence, f["issuer"].status) == (0.55, "doubtful")


def test_box_is_the_union_of_the_cited_words():
    f = by_name(ground_fields(reply(full_name=("Ms Ananya Mehta", ["w1", "w2", "w3"])), WORDS))["full_name"]
    assert f.box == [0.10, 0.20, 0.30, 0.22]
    assert f.page_text == "Ms Ananya Mehta" and f.note == ""


def test_punctuation_and_case_do_not_matter():
    f = by_name(ground_fields(reply(full_name=("MS ANANYA, MEHTA.", ["w1", "w2", "w3"])), WORDS))["full_name"]
    assert f.status == "ok" and f.value == "MS ANANYA, MEHTA."


def test_a_value_the_page_does_not_show_is_never_trusted():
    f = by_name(ground_fields(reply(statement_date=("08 Sep 2026", ["w4", "w5", "w6"])), WORDS))["statement_date"]
    assert (f.status, f.confidence) == ("not_on_page", 0.0)
    assert f.value == "08 Sep 2026" and f.page_text == "09 Sep 2026"
    assert f.note == 'The page says "09 Sep 2026"'
    assert f.box == [0.60, 0.18, 0.75, 0.21]


def test_no_words_from_the_page_means_not_on_page():
    f = by_name(ground_fields(reply(issuer=("Lumenvale Energy", ["w99", "x"])), WORDS))["issuer"]
    assert (f.status, f.confidence, f.box) == ("not_on_page", 0.0, None)
    assert f.note == "The model gave no words from the page"


def test_missing_and_empty_fields():
    f = by_name(ground_fields(reply(address=("  ", [])), WORDS))
    for name in ("address", "issuer"):
        assert (f[name].status, f[name].value, f[name].confidence) == ("missing", "", 0.0)
        assert f[name].note == "Not found on the page"


def test_api_shows_grounded_fields_for_a_case():
    data = TestClient(app).get("/api/cases/D03-014").json()
    f = {x["name"]: x for x in data["fields"]}
    assert f["full_name"]["status"] == "ok" and f["full_name"]["box"]
    assert f["statement_date"]["status"] == "not_on_page"
    assert f["statement_date"]["note"] == 'The page says "30 Sep 2026"'
