"""Tests for scripts/eval_prompt.py. A fake client stands in for the API."""

import csv

import pytest

from scripts import eval_prompt as ev
from tests.fakes import FakeClient

TEMPLATE = "Do it.\n{text}"


def test_normalise_keeps_first_word_lowercase():
    assert ev.normalise("Label: Billing.") == "label"
    assert ev.normalise("  Access. ") == "access"
    assert ev.normalise(None) == ""


def test_exact_scores_matching_labels_and_lists_misses():
    rows = [{"text": "a", "label": "access"}, {"text": "b", "label": "network"}]
    client = FakeClient("access", "hardware")
    acc, misses = ev.evaluate(rows, TEMPLATE, client)
    assert acc == 0.5
    assert misses == [("b", "network", "hardware")]


def test_exact_sends_text_at_temperature_zero():
    client = FakeClient("access")
    ev.evaluate([{"text": "locked out", "label": "access"}], TEMPLATE, client)
    call = client.calls[0]
    assert call["temperature"] == 0
    assert call["messages"][0]["content"] == "Do it.\nlocked out"


def test_split_points_drops_blanks():
    assert ev.split_points(" a ; b|c ;; ") == ["a", "b|c"]
    assert ev.split_points("") == []


def test_point_found_ignores_case_and_accepts_alternatives():
    assert ev.point_found("reran|re-ran", "The agent RERAN the job")
    assert ev.point_found("reran|re-ran", "then re-ran it")
    assert not ev.point_found("reran|re-ran", "nothing tried")
    assert not ev.point_found("x", None)


def test_detect_mode_reads_header():
    assert ev.detect_mode([{"text": "a", "expected_points": "b"}]) == "checklist"
    assert ev.detect_mode([{"text": "a", "label": "b"}]) == "exact"


def test_checklist_counts_points_found_across_rows():
    rows = [
        {"text": "t1", "expected_points": "timeout;reran|re-ran;platform"},
        {"text": "t2", "expected_points": "printer;technician"},
    ]
    client = FakeClient("- Timeout on export\n- Reran it\n- next step unclear", "printer and technician")
    acc, misses = ev.evaluate(rows, TEMPLATE, client, mode="checklist")
    assert acc == pytest.approx(4 / 5)
    assert len(misses) == 1
    text, missing, answer = misses[0]
    assert text == "t1"
    assert missing == "platform"
    assert "Timeout" in answer


def test_checklist_all_points_found_gives_full_score():
    rows = [{"text": "t", "expected_points": "a;b"}]
    acc, misses = ev.evaluate(rows, TEMPLATE, FakeClient("A and B"), mode="checklist")
    assert acc == 1.0
    assert misses == []


def test_checklist_handles_empty_reply():
    rows = [{"text": "t", "expected_points": "a"}]
    acc, misses = ev.evaluate(rows, TEMPLATE, FakeClient(None), mode="checklist")
    assert acc == 0.0
    assert misses[0][1] == "a"


def test_empty_test_set_and_bad_mode_raise():
    with pytest.raises(ValueError):
        ev.evaluate([], TEMPLATE, FakeClient("x"))
    with pytest.raises(ValueError):
        ev.evaluate([{"text": "a", "label": "b"}], TEMPLATE, FakeClient("x"), mode="fuzzy")


def test_log_run_keeps_format_and_writes_header_once(tmp_path):
    path = tmp_path / "logs" / "runs.csv"
    ev.log_run("classify", "v1", "m", 0.8, path=str(path))
    ev.log_run("handover_note", "v2", "m", 0.75, path=str(path))
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["timestamp", "prompt", "version", "model", "accuracy"]
    assert rows[1][1:] == ["classify", "v1", "m", "0.8"]
    assert rows[2][1:] == ["handover_note", "v2", "m", "0.75"]
    assert len(rows) == 3


def test_load_rows_reads_multiline_cells(tmp_path):
    path = tmp_path / "t.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        f.write('text,expected_points\n"line1\nline2",a;b\n')
    rows = ev.load_rows(path)
    assert rows[0]["text"] == "line1\nline2"
    assert rows[0]["expected_points"] == "a;b"


def test_main_scores_checklist_csv_and_logs_run(tmp_path, monkeypatch, capsys):
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "demo_v1.txt").write_text("Summarise: {text}", encoding="utf-8")
    with open(tmp_path / "t.csv", "w", newline="", encoding="utf-8") as f:
        f.write("text,expected_points\nhello,alpha;beta\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(ev, "get_client", lambda: FakeClient("alpha only"))
    monkeypatch.setattr("sys.argv", ["eval_prompt", "demo", "v1", "--data", "t.csv"])
    ev.main()
    out = capsys.readouterr().out
    assert "mode: checklist" in out
    assert "accuracy: 50%" in out
    assert "missing=beta" in out
    with open(tmp_path / "data" / "prompt_runs.csv", newline="") as f:
        assert list(csv.reader(f))[1][1:3] == ["demo", "v1"]


def test_get_client_requires_key_and_retries_rate_limits(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        ev.get_client()
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    assert ev.get_client().max_retries == 8
