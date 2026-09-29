import csv

from app.chatbot import Backend
from scripts.benchmark import FIELDS, read_prompts, run_benchmark, summarise, write_csv
from tests.fakes import FakeClient, timeout


def test_benchmark_rows_cost_and_summary(tmp_path):
    backends = {
        "a": Backend(FakeClient("ans a"), "model-a", 1.0, 5.0),
        "b": Backend(FakeClient(timeout()), "model-b", 3.0, 15.0),
    }
    ticks = iter(range(0, 100, 2))  # every call "takes" 2 seconds
    rows = run_benchmark(backends, ["p1", "p2"], clock=lambda: next(ticks))
    assert len(rows) == 4
    a = [r for r in rows if r["backend"] == "a"]
    assert a[0]["answer"] == "ans a" and a[0]["seconds"] == 2
    # FakeClient usage: 10 in, 5 out -> 10/1e6*1 + 5/1e6*5
    assert a[0]["cost"] == round(10e-6 + 25e-6, 6)
    assert rows[1]["answer"].startswith("ERROR")  # failure recorded, run continues
    s = summarise(rows)
    assert s["a"]["calls"] == 2 and s["a"]["avg_seconds"] == 2
    assert round(s["a"]["total_cost"], 6) == 70e-6

    path = tmp_path / "b.csv"
    write_csv(rows, path)
    with open(path, encoding="utf-8") as f:
        assert set(next(csv.DictReader(f))) == set(FIELDS)


def test_read_prompts_skips_blank_lines(tmp_path):
    f = tmp_path / "p.txt"
    f.write_text("one\n\n two \n", encoding="utf-8")
    assert read_prompts(f) == ["one", "two"]
