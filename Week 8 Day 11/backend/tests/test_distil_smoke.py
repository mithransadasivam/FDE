"""Day 11: the parts that are done. These pass from the start."""

import numpy as np
from fastapi.testclient import TestClient

from app.distil import cascade, features, model, reads
from app.distil.reads import words_of
from app.main import app
from tests.distilkit import read


def test_the_teacher_reads_load():
    pilot, ct = reads.load("pilot"), reads.load("council_tax")
    assert len(pilot) == 1500 and len(ct) == 300
    assert {r["kind"] for r in pilot} == {"utility_bill", "bank_statement"} and {r["kind"] for r in ct} == {"council_tax"}
    s = reads.summary("pilot")
    assert s["all_agree"] < s["reads"] and set(s["disagree_by_field"]) == {"full_name", "address", "statement_date", "issuer"}


def test_a_word_has_the_features_the_slides_describe():
    ws = words_of(read())
    f = features.word_features(ws, 12, "bank_statement")  # "06" in "Statement date 06 Oct 2026"
    assert {"w=<num>", "shape=dd", "daynum", "p1=date", "p2=statement", "n1=oct", "kind=bank_statement"} <= set(f)


def test_a_model_trains_saves_and_loads():
    rs = reads.load("pilot")[:40]
    m = model.train("smoke", rs, ["pilot"])
    again = model.load("smoke")
    ws = words_of(rs[0])
    p = again.probs(ws, rs[0]["kind"])
    assert p.shape == (len(ws), len(again.classes)) and np.allclose(p.sum(axis=1), 1.0)
    assert np.allclose(p, m.probs(ws, rs[0]["kind"]), atol=1e-3)
    assert again.meta["reads"] == 40 and again.meta["train_seconds"] >= 0


def test_spot_checks_are_the_same_every_time():
    ids = [f"B-{i:03d}" for i in range(1, 401)]
    picked = [d for d in ids if cascade.spot_check(d)]
    assert picked == [d for d in ids if cascade.spot_check(d)]
    assert 8 <= len(picked) <= 35  # about one in twenty


def test_the_model_lab_api_answers():
    c = TestClient(app)
    s = c.get("/api/distil/status").json()
    assert set(s["tickets"]) == {"ENG-1101", "ENG-1102", "ENG-1103"}
    assert [r["name"] for r in s["read_files"]] == ["pilot", "council_tax"]
    assert s["volumes"]["business_as_usual_docs_per_month"] == 8600
    assert c.get("/api/distil/reads/pilot?n=3").json()["summary"]["reads"] == 1500
