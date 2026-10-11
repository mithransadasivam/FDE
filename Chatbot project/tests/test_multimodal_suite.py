"""The multimodal test set (Day 10 exercise, Phase 33): the answer key matches the files, and the hard cases are really there."""
import csv
import re
import wave
from collections import Counter

import numpy as np
import pytest
from pypdf import PdfReader

from app.config import DOCS_DIR, ROOT
from app.loader import load_documents
from PIL import Image

SUITE = ROOT / "data" / "multimodal_suite.csv"
BASE = ROOT / "data" / "multimodal"
COLUMNS = ["id", "kind", "file", "question", "expected_error_code", "expected_application", "expected_severity", "expected_answer", "expected_source", "notes"]


@pytest.fixture(scope="module")
def rows():
    with open(SUITE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == COLUMNS
        return list(reader)


def test_the_suite_has_at_least_fourteen_unique_rows_of_three_kinds(rows):
    assert len(rows) >= 14
    assert len({r["id"] for r in rows}) == len(rows)
    assert Counter(r["kind"] for r in rows).keys() == {"screenshot", "scan", "voice"}


def test_every_file_the_suite_names_exists_and_is_small(rows):
    for r in rows:
        path = BASE / r["file"]
        assert path.is_file(), r["file"]
        assert path.stat().st_size < 1_500_000, r["file"]


def test_there_are_at_least_eight_real_error_screenshots_whose_codes_are_in_the_documents(rows):
    reference = " ".join(text for d in load_documents(DOCS_DIR) if d["source"].startswith("Day07") for _, text in d["pages"])
    clear = [r for r in rows if r["kind"] == "screenshot" and r["expected_error_code"] and not r["file"].endswith(("injection_note.png", "injection_small.png"))]
    assert len(clear) >= 8
    for r in clear:
        assert r["expected_error_code"] in reference, r["id"]
        assert r["expected_severity"] in {"P1", "P2", "P3", "P4"} and r["expected_answer"] and r["expected_source"]


def test_the_hard_screenshots_are_there_on_purpose(rows):
    by_file = {r["file"].split("/")[-1]: r for r in rows}
    assert by_file["hard_no_code.png"]["expected_error_code"] == ""                   # an image with no error code
    tiny = Image.open(BASE / by_file["hard_tiny_blurry.png"]["file"])
    assert max(tiny.size) <= 200                                                      # a tiny, blurred image
    assert "landscape" in by_file["hard_not_it.png"]["expected_answer"]               # nothing to do with IT: must be declined
    assert "Summer2026" in by_file["hard_injection_note.png"]["notes"]                # a note in the picture that gives orders
    assert "CANARY" in by_file["hard_injection_small.png"]["notes"]                   # orders in tiny corner text
    assert Image.open(BASE / by_file["hard_injection_small.png"]["file"]).size[0] >= 1000


def test_at_least_two_scans_are_picture_only_and_have_three_or_more_questions_only_the_scan_can_answer(rows):
    scans = [r for r in rows if r["kind"] == "scan"]
    assert len(scans) >= 3 and len({r["file"] for r in scans}) >= 2
    for name in {r["file"] for r in scans}:
        reader = PdfReader(BASE / name)
        assert sum(len((page.extract_text() or "").strip()) for page in reader.pages) == 0, f"{name} has a text layer: it is not a scan"
    knowledge = " ".join(text for d in load_documents(DOCS_DIR, use_transcripts=False) for _, text in d["pages"]).lower()
    for r in scans:
        assert "150 colour pages" not in knowledge and "escorted" not in knowledge  # the facts are in the scans only


def test_there_are_at_least_four_voice_notes_one_with_a_spelled_code_one_noisy_one_silent(rows):
    voices = [r for r in rows if r["kind"] == "voice"]
    assert len(voices) >= 4
    assert any("spelled out" in r["notes"] and r["expected_error_code"] for r in voices)
    assert any("noise" in r["notes"] for r in voices)
    silent = [r for r in voices if "silent" in r["notes"]]
    assert len(silent) == 1
    for r in voices:
        with wave.open(str(BASE / r["file"])) as w:
            samples = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
            assert w.getnframes() / w.getframerate() < 15, r["file"]
        if r in silent:
            assert np.abs(samples).max() == 0
        else:
            assert 1000 < np.abs(samples).max() < 32767, f"{r['file']} is silent or clipped"


def test_nothing_in_the_set_is_real_or_personal(rows):
    text = " ".join(" ".join(r.values()) for r in rows)
    assert not re.search(r"[A-Za-z0-9._-]+@(?!northwind\.example)[A-Za-z0-9.-]+", text)  # no real e-mail address
