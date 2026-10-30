"""Day 4 prompt 8: the governance pack is built from real evidence and refuses to fill a gap by hand."""
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts import build_governance as bg
from scripts import governance_pack as gp

ROOT = Path(__file__).resolve().parent.parent


def _skeleton():
    base = bg.risks() + [dict(zip(("id", "risk", "nist_function", "likelihood", "impact", "owner", "control", "evidence"), r), review_date=bg.REVIEW) for r in gp.NEW]
    return [{"id": r["id"], "control_file": gp.CONTROLS[r["id"]][0], "control_function": gp.CONTROLS[r["id"]][1], "tests": gp.CONTROLS[r["id"]][2]} for r in base]


def test_there_are_at_least_twelve_risks_and_each_has_a_control_a_test_and_an_owner():
    rows = _skeleton()
    assert len(rows) >= 12
    for r in bg.risks():
        assert r["owner"] and r["control"] and r["nist_function"] in {"Govern", "Map", "Measure", "Manage"}
    assert all(r["control_file"] and r["control_function"] and r["tests"] for r in rows)
    topics = " ".join(r["risk"].lower() for r in bg.risks()) + " ".join(n[1].lower() for n in gp.NEW)
    for need in ("name, gender or age", "transcription", "hidden in a cv", "fabricated quote", "forbidden question", "over-rely", "leaks private data", "kept longer", "cost", "model accuracy changes"):
        assert need in topics, need


def test_every_control_and_test_the_register_names_really_exists():
    assert gp.verify_controls(_skeleton()) == []


def test_a_control_or_test_that_does_not_exist_is_caught():
    rows = _skeleton()
    rows[0] = {**rows[0], "control_function": "no_such_function"}
    rows[1] = {**rows[1], "tests": ["tests/test_accent_test.py::test_that_was_never_written"]}
    rows[2] = {**rows[2], "control_file": "app/nothing_here.py"}
    rows[3] = {**rows[3], "tests": []}
    problems = " ".join(gp.verify_controls(rows))
    assert "no_such_function" in problems and "test_that_was_never_written" in problems and "nothing_here.py" in problems and "no test is named" in problems


@pytest.fixture
def reports_dir(tmp_path, monkeypatch):
    for name, *_ in gp.REQUIRED_REPORTS:
        doc = {"report": name, "date": datetime.now(timezone.utc).isoformat(timespec="seconds"), "passed": True, "results": {}, "settings": {}}
        (tmp_path / f"{name}.json").write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(gp, "REPORTS", tmp_path)
    return tmp_path


def test_fresh_reports_load(reports_dir):
    reports, gaps = gp.load_reports(False)
    assert len(reports) == len(gp.REQUIRED_REPORTS) and gaps == []


def test_a_missing_report_stops_the_pack_with_a_clear_message_and_the_command_to_run(reports_dir):
    (reports_dir / "accent_test.json").unlink()
    with pytest.raises(gp.PackError) as e:
        gp.load_reports(False)
    msg = str(e.value)
    assert "Accent test" in msg and "no report" in msg and "python -m evals.accent_test" in msg


def test_a_report_older_than_seven_days_stops_the_pack(reports_dir):
    p = reports_dir / "identity_swap.json"
    doc = json.loads(p.read_text())
    doc["date"] = (datetime.now(timezone.utc) - timedelta(days=9)).isoformat(timespec="seconds")
    p.write_text(json.dumps(doc))
    with pytest.raises(gp.PackError) as e:
        gp.load_reports(False)
    assert "Identity swap" in str(e.value) and "9 days old" in str(e.value)


def test_with_allow_gaps_the_missing_report_is_listed_as_not_yet_tested(reports_dir):
    (reports_dir / "copilot_eval.json").unlink()
    reports, gaps = gp.load_reports(True)
    assert "copilot_eval" not in reports and gaps[0]["label"] == "Copilot evaluation"
    md = gp.evidence_md(reports, gaps, {"summary": "1 passed", "results": {}, "full": False, "at": "now"}, [])
    assert "not yet tested" in md and "Copilot evaluation" in md


def test_oversight_is_read_from_the_supervisors_table():
    from app.supervisor import ALLOWED, PERSON

    md = gp.oversight_md()
    persons = sum(1 for moves in ALLOWED.values() for who in moves.values() if who == PERSON)
    section = md.split("## Moves only a person can make")[1].split("## Automatic")[0]
    assert section.count("| ") // 2 >= persons and "SCREENED | SHORTLISTED" in section and "approve_and_send" in md


def test_the_classification_proves_no_emotion_recognition_from_the_code_and_the_settings():
    md = gp.classification_md({})
    assert "Article 5(1)(f)" in md and "Fields about a camera, video, emotion" in md and "**none**" in md and "0 match(es)" in md
    assert "score_text(" in md and "getUserMedia({audio: true})" in md and "Annex III" in md and "NOTICE" in md or "interviewer" in md


def test_the_model_card_names_every_agent_with_its_tools_and_what_it_must_never_do():
    md = gp.model_card_md({}, [])
    for agent in ("supervisor", "requisition", "document", "screening", "interviewer", "copilot", "assistant", "communications", "compliance"):
        assert f"| {agent} |" in md
    assert "It must never: call any of the other" in md and "Known limits, taken from the reports" in md and "Known limitations" in md


def test_the_html_is_one_self_contained_file_with_every_document():
    html = gp.combined_html([("classification", "# A\n\n| x | y |\n|---|---|\n| 1 | `2` |\n\n- **b**"), ("oversight", "# B")])
    assert html.count("<section") == 2 and "<table>" in html and "<code>2</code>" in html and "<strong>b</strong>" in html and "<script" not in html and "http" not in html.split("<main>")[0]


def test_the_built_pack_has_the_five_documents_and_the_combined_html():
    gov = ROOT / "governance"
    if not (gov / "evidence.md").exists():
        pytest.skip("run python -m scripts.governance_pack first")
    for f in ("classification.md", "model_card.md", "risk_register.md", "evidence.md", "oversight.md", "governance_pack.html"):
        assert (gov / f).exists() and (gov / f).stat().st_size > 500, f
    csvtext = (gov / "risk_register.csv").read_text(encoding="utf-8")
    assert csvtext.count("\nR-") >= 12 and "latest_result" in csvtext
