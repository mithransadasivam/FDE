import pytest

from app.retrieval_eval import (
    check_evidence,
    load_retrieval_set,
    run_eval,
    save_eval,
    score_row,
    summarize,
)

EVIDENCE = "kept for 30 days"


def chunk(source, text, page=1):
    return {"source": source, "text": text, "page": page}


RIGHT = chunk("backup.md", "Daily backups are kept for 30 days.")
WRONG_TEXT = chunk("backup.md", "Monthly backups are kept for 12 months.")
OTHER_DOC = chunk("other.md", "Daily backups are kept for 30 days.")


# ---- the scoring function ----
def test_found_first():
    assert score_row([RIGHT, WRONG_TEXT], "backup.md", EVIDENCE, k=4) == {"rank": 1, "hit": True, "rr": 1.0}


def test_found_lower_down_but_within_k():
    result = score_row([WRONG_TEXT, OTHER_DOC, RIGHT], "backup.md", EVIDENCE, k=4)
    assert result == {"rank": 3, "hit": True, "rr": pytest.approx(1 / 3)}


def test_found_below_k_is_not_a_hit_but_keeps_its_reciprocal_rank():
    chunks = [WRONG_TEXT] * 5 + [RIGHT]
    result = score_row(chunks, "backup.md", EVIDENCE, k=4)
    assert result["rank"] == 6 and result["hit"] is False and result["rr"] == pytest.approx(1 / 6)


def test_not_found_at_all():
    assert score_row([WRONG_TEXT, OTHER_DOC], "backup.md", EVIDENCE, k=4) == {"rank": None, "hit": False, "rr": 0.0}


def test_right_text_from_the_wrong_document_does_not_count():
    assert score_row([OTHER_DOC], "backup.md", EVIDENCE, k=4)["rank"] is None


def test_case_and_line_breaks_are_ignored():
    messy = chunk("backup.md", "Daily backups are KEPT\nfor   30\ndays.")
    assert score_row([messy], "backup.md", EVIDENCE, k=4)["rank"] == 1


def test_empty_result_list():
    assert score_row([], "backup.md", EVIDENCE, k=4)["rank"] is None


# ---- the test set file ----
GOOD_CSV = (
    "question,previous_question,kind,expected_source,evidence,expected_answer\n"
    "How long?,,plain,backup.md,kept for 30 days,30 days\n"
    "And monthly?,How long?,follow-up,backup.md,12 months,12 months\n"
)


def test_load_retrieval_set(tmp_path):
    f = tmp_path / "set.csv"
    f.write_text(GOOD_CSV, encoding="utf-8")
    rows = load_retrieval_set(f)
    assert len(rows) == 2 and rows[1]["previous_question"] == "How long?"


@pytest.mark.parametrize("text", [
    "question,kind\nHow?,plain\n",                                                                   # missing columns
    GOOD_CSV.replace("plain", "easy"),                                                               # unknown kind
    GOOD_CSV.replace("kept for 30 days", ""),                                                        # empty evidence
])
def test_bad_test_sets_are_rejected(tmp_path, text):
    f = tmp_path / "set.csv"
    f.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        load_retrieval_set(f)


def test_evidence_check_reports_missing_phrase_and_missing_document(tmp_path):
    (tmp_path / "backup.md").write_text("Daily backups are kept\nfor 30 days.", encoding="utf-8")
    rows = [
        {"question": "q1", "kind": "plain", "expected_source": "backup.md", "evidence": "kept for 30 days"},
        {"question": "q2", "kind": "plain", "expected_source": "backup.md", "evidence": "kept for 99 days"},
        {"question": "q3", "kind": "plain", "expected_source": "gone.md", "evidence": "anything"},
    ]
    missing = check_evidence(rows, tmp_path)
    assert [m["question"] for m in missing] == ["q2", "q3"]
    assert "not in the document" in missing[0]["problem"] and "not found" in missing[1]["problem"]


# ---- running and summarising ----
def make_rows():
    return [
        {"question": "q1", "previous_question": "", "kind": "plain", "expected_source": "backup.md", "evidence": EVIDENCE},
        {"question": "q2", "previous_question": "", "kind": "plain", "expected_source": "backup.md", "evidence": EVIDENCE},
        {"question": "q3", "previous_question": "q2", "kind": "follow-up", "expected_source": "backup.md", "evidence": EVIDENCE},
        {"question": "q4", "previous_question": "", "kind": "messy", "expected_source": "backup.md", "evidence": EVIDENCE},
    ]


def fake_retrieve(row):
    return {
        "q1": [RIGHT],                                      # rank 1
        "q2": [WRONG_TEXT, WRONG_TEXT, RIGHT],              # rank 3
        "q3": [WRONG_TEXT] * 4 + [RIGHT],                   # rank 5: outside k=4
        "q4": [WRONG_TEXT],                                 # not found
    }[row["question"]]


def test_run_eval_and_summary():
    results = run_eval(make_rows(), fake_retrieve, k=4)
    assert [r["rank"] for r in results] == [1, 3, 5, None]
    assert [r["hit"] for r in results] == [True, True, False, False]
    s = summarize(results)
    assert s["questions"] == 4 and s["hits"] == 2 and s["hit_rate"] == 0.5
    assert s["mrr"] == pytest.approx((1 + 1 / 3 + 1 / 5 + 0) / 4, abs=1e-3)
    assert s["by_kind"] == {"plain": {"hits": 2, "total": 2}, "follow-up": {"hits": 0, "total": 1}, "messy": {"hits": 0, "total": 1}}


def test_retrieve_function_receives_the_whole_row():
    seen = []
    run_eval(make_rows(), lambda row: seen.append(row["previous_question"]) or [], k=4)
    assert seen == ["", "", "q2", ""]


def test_depth_limits_how_many_chunks_are_scored():
    results = run_eval(make_rows()[2:3], fake_retrieve, k=4, depth=4)
    assert results[0]["rank"] is None  # the right chunk was at position 5, beyond the depth


def test_summary_of_nothing_does_not_crash():
    assert summarize([])["hit_rate"] == 0.0


def test_save_eval_writes_csv_and_json(tmp_path):
    import json

    path = save_eval(run_eval(make_rows(), fake_retrieve, k=4), "vector", 4, tmp_path)
    assert path.name == "vector.csv" and path.exists()
    saved = json.loads((tmp_path / "vector.json").read_text(encoding="utf-8"))
    assert saved["mode"] == "vector" and saved["hits"] == 2 and saved["k"] == 4


def test_pause_between_rows_only_and_not_counted_in_time():
    waits = []
    results = run_eval(make_rows(), fake_retrieve, k=4, pause=3, sleep=waits.append)
    assert waits == [3, 3, 3] and all(r["seconds"] < 1 for r in results)


def test_rerank_fallback_is_recorded_and_counted():
    def fallback(row):
        return [{**RIGHT, "rerank_score": None}]

    def worked(row):
        return [{**RIGHT, "rerank_score": 8.0}]

    rows = make_rows()[:2]
    assert [r["rerank_fallback"] for r in run_eval(rows, fallback, k=4)] == [True, True]
    results = run_eval(rows, worked, k=4)
    assert [r["rerank_fallback"] for r in results] == [False, False] and summarize(results)["rerank_fallbacks"] == 0
    assert summarize(run_eval(rows, fallback, k=4))["rerank_fallbacks"] == 2
