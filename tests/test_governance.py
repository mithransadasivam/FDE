"""Phase 9: the governance pack is data, and a script fails when it is incomplete."""
import json
import shutil
from pathlib import Path

import pytest

from scripts import governance_check as gc

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def pack(tmp_path):
    """A copy of the repository's governance files and reports, so tests can break things safely."""
    for rel in ("governance", "reports", "EVAL_REPORT.md", "PERF_REPORT.md", "SECURITY_FINDINGS.md"):
        src = REPO / rel
        if src.is_dir():
            shutil.copytree(src, tmp_path / rel, ignore=shutil.ignore_patterns("evidence"))
        elif src.exists():
            shutil.copy(src, tmp_path / rel)
    return tmp_path


def test_the_pack_in_the_repository_passes():
    assert gc.check(REPO, do_collect=True) == []


def test_it_fails_when_one_field_of_the_model_card_is_emptied(pack):
    card = json.loads((pack / "governance" / "model_card.json").read_text(encoding="utf-8"))
    card["human_oversight"] = ""
    (pack / "governance" / "model_card.json").write_text(json.dumps(card), encoding="utf-8")
    errs = gc.check(pack)
    assert any("human_oversight" in e and "empty" in e for e in errs)


def test_it_fails_on_a_nested_empty_field(pack):
    card = json.loads((pack / "governance" / "model_card.json").read_text(encoding="utf-8"))
    card["data"]["personal_data"] = "  "
    (pack / "governance" / "model_card.json").write_text(json.dumps(card), encoding="utf-8")
    assert any("data.personal_data" in e for e in gc.check(pack))


def test_it_fails_when_a_template_field_is_missing(pack):
    card = json.loads((pack / "governance" / "model_card.json").read_text(encoding="utf-8"))
    del card["contact"]
    (pack / "governance" / "model_card.json").write_text(json.dumps(card), encoding="utf-8")
    assert any("'contact'" in e and "missing" in e for e in gc.check(pack))


def test_it_fails_when_a_number_in_the_card_is_not_in_any_report(pack):
    card = json.loads((pack / "governance" / "model_card.json").read_text(encoding="utf-8"))
    card["evaluation"]["p95_seconds"] = "987.65 s"
    (pack / "governance" / "model_card.json").write_text(json.dumps(card), encoding="utf-8")
    assert any("p95_seconds" in e for e in gc.check(pack))


def test_it_fails_when_an_evidence_file_changes_after_the_manifest(pack):
    assert gc.check(pack) == []
    ev = pack / "governance" / "evidence" / "EVAL_REPORT.md"
    ev.write_text(ev.read_text(encoding="utf-8") + "\nedited after the manifest was made\n", encoding="utf-8")
    assert any("EVAL_REPORT.md does not match its SHA-256" in e for e in gc.check(pack, do_collect=False))


def test_it_fails_when_a_risk_has_no_owner_or_review_date_or_evidence(pack):
    reg = json.loads((pack / "governance" / "risk_register.json").read_text(encoding="utf-8"))
    reg["risks"][0]["owner"] = ""
    reg["risks"][1]["review_by"] = "someday"
    reg["risks"][2]["evidence"] = ["NOPE.md: nothing"]
    (pack / "governance" / "risk_register.json").write_text(json.dumps(reg), encoding="utf-8")
    errs = gc.check(pack)
    assert any("owner" in e for e in errs) and any("review_by" in e for e in errs) and any("NOPE.md" in e for e in errs)


def test_it_fails_with_fewer_than_six_risks(pack):
    reg = json.loads((pack / "governance" / "risk_register.json").read_text(encoding="utf-8"))
    reg["risks"] = reg["risks"][:3]
    (pack / "governance" / "risk_register.json").write_text(json.dumps(reg), encoding="utf-8")
    assert any("at least 6" in e for e in gc.check(pack))


def test_quoted_evidence_must_really_be_in_the_report(pack):
    reg = json.loads((pack / "governance" / "risk_register.json").read_text(encoding="utf-8"))
    reg["risks"][0]["evidence"] = ["SECURITY_FINDINGS.md: a sentence that is not in the file anywhere 12345"]
    (pack / "governance" / "risk_register.json").write_text(json.dumps(reg), encoding="utf-8")
    assert any("does not appear" in e for e in gc.check(pack))


def test_risk_register_uses_the_template_fields_and_nist_functions():
    reg = json.loads((REPO / "governance" / "risk_register.json").read_text(encoding="utf-8"))["risks"]
    tpl = json.loads((REPO / "governance" / "risk_register_template.json").read_text(encoding="utf-8"))["risks"][0]
    assert len(reg) >= 6 and all(set(tpl) <= set(r) for r in reg)
    assert {r["nist_function"] for r in reg} <= gc.NIST


def test_classification_names_the_deciding_article():
    text = (REPO / "governance" / "classification.md").read_text(encoding="utf-8")
    for must in ("Article 5", "Annex I", "Annex III", "Article 6(3)", "Article 50"):
        assert must in text


def test_hashes_do_not_depend_on_line_endings(pack, tmp_path):
    # a fresh clone on another machine may check the files out with CRLF or LF; the manifest must still match
    assert gc.check(pack) == []
    ev = pack / "governance" / "evidence" / "EVAL_REPORT.md"
    ev.write_bytes(ev.read_bytes().replace(b"\n", b"\r\n"))
    assert gc.check(pack, do_collect=False) == []
