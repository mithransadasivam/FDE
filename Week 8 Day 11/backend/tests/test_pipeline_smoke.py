"""Day 6 smoke tests: they pass before and after the tickets. Run: python -m pytest -q tests/test_pipeline_smoke.py"""

from fastapi.testclient import TestClient

from app.main import app
from app.pipeline import documents as D
from app.pipeline import service as S
from app.pipeline.batch import Job, simulate
from app.pipeline.methods import locate_value, method_of
from app.prototype.models import OcrWord

client = TestClient(app)


def test_the_october_batch_has_200_documents_and_800_keyed_fields():
    m = D.manifest("october")
    assert len(m) == 200
    assert sum(r["file"].endswith(".pdf") for r in m) == 120
    assert len(D.keyed("october")) == 800
    assert all(D.document_file(r["doc_id"]).exists() and D.page_image(r["doc_id"]).exists() for r in m)


def test_the_human_bar_comes_from_the_double_keying():
    h = S.human_bar("october")
    assert h["one_keyer"] == 98.6 and h["agreement"] == 97.1 and h["settled_by_tom"] == 23


def test_status_lists_the_prompts_and_prices():
    s = client.get("/api/pipeline/status").json()
    assert "extract_v2" in s["prompts"]["parser"] and "extract_vlm_v0" in s["prompts"]["vision"]
    assert any(p["model_id"] == "anthropic/claude-haiku-5.5" for p in s["prices"])


def test_the_documents_screen_opens_before_and_after_eng_601():
    d = client.get("/api/pipeline/documents?set=october").json()
    assert len(d["documents"]) == 200 and d["files"] == {"pdf": 120, "jpg": 80}
    assert d["not_built"] == "" or "ENG-601" in d["not_built"]


def test_the_page_images_are_served():
    r = client.get("/api/pipeline/documents/B-001/image")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"


def test_vision_prompts_are_recognised_by_name():
    assert method_of("extract_vlm_v0") == "vision" and method_of("extract_v2") == "parser"


def test_locate_value_finds_words_across_interleaved_columns():
    words = [OcrWord(id=f"w{i}", text=t, box=[0, 0, 1, 1], confidence=0.9) for i, t in
             enumerate(["99", "Leckhampton", "Road", "Statement", "date", "Cheltenham", "GL52", "4QY"])]
    assert locate_value("99 Leckhampton Road, Cheltenham, GL52 4QY", words) == ["w0", "w1", "w2", "w5", "w6", "w7"]
    assert locate_value("99 Leckhampton Rd, Cheltenham, GL52 4QY", words) == []


def test_the_scripted_provider_accepts_eight_calls_at_once():
    jobs = [Job(key=f"d{i}", run=(lambda i=i: {"i": i}), latency_ms=2000) for i in range(40)]
    eight = simulate(jobs, 8)
    assert len(eight.done) == 40 and eight.refusals == 0 and eight.wall_ms == 10000
    sixteen = simulate(jobs, 16)
    assert sixteen.refusals > 0 and len(sixteen.done) + len(sixteen.failed) == 40


def test_the_review_queue_opens_with_no_run_yet():
    q = client.get("/api/pipeline/queue?set=october").json()
    assert q["items"] == [] or q["open"] >= 0
