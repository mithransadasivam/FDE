"""The teacher's answers (done: you do not change this file for a ticket).

Since ADR-003 the pilot has read every document twice with Sonnet 5: the parser reading (extract_v2, which cites
the OCR words it used) and the vision reading (extract_vlm_v1, a value only). Each read is kept with the words it
was given. Those reads are the training data for the small model: Sonnet is the teacher, the small model the student.

A read, as stored (one JSON object per line):
  doc_id, read_on (the month), kind (utility_bill, bank_statement, council_tax), issuer, source (text_layer or ocr),
  words: [[id, text, x0, y0, x1, y1, ocr_confidence], ...] in reading order,
  parser: {field: {"value", "word_ids"}},   vision: {field: value}

The teacher is not always right. Nobody keyed these documents: the only check is whether the two readings agree.
"""

import json
from collections import Counter
from functools import lru_cache
from pathlib import Path

from app.config import COUNCIL_TAX_READS_FILE_11, TEACHER_READS_FILE_11
from app.prototype.models import FIELDS, OcrWord

READ_FILES = {
    "pilot": {"file": TEACHER_READS_FILE_11, "label": "The pilot's reads, November and December: bills and bank statements"},
    "council_tax": {"file": COUNCIL_TAX_READS_FILE_11, "label": "The pilot's reads of council tax bills, January (homework)"},
}


def norm(text: str) -> str:
    return "".join(ch for ch in (text or "").lower() if ch.isalnum())


@lru_cache(maxsize=8)
def _load(path: str, _mtime: float) -> tuple:
    with open(path, encoding="utf-8") as f:
        return tuple(json.loads(line) for line in f if line.strip())


def load(name: str) -> list[dict]:
    """Every read in one file of reads ("pilot" or "council_tax")."""
    p = Path(READ_FILES[name]["file"])
    return list(_load(str(p), p.stat().st_mtime)) if p.exists() else []


def load_many(names: list[str]) -> list[dict]:
    return [r for n in names for r in load(n)]


def words_of(read: dict) -> list[OcrWord]:
    return [OcrWord(id=w[0], text=w[1], box=w[2:6], confidence=w[6]) for w in read["words"]]


def agree(read: dict, field: str) -> bool:
    """Do the teacher's two readings give the same value for this field?"""
    return norm(read["parser"][field]["value"]) == norm(read["vision"][field])


def summary(name: str) -> dict:
    rs = load(name)
    kinds = Counter(r["kind"] for r in rs)
    disagree = Counter(f for r in rs for f in FIELDS if not agree(r, f))
    all_agree = sum(all(agree(r, f) for f in FIELDS) for r in rs)
    return {"name": name, "label": READ_FILES[name]["label"], "file": Path(READ_FILES[name]["file"]).name, "reads": len(rs),
            "kinds": dict(kinds), "sources": dict(Counter(r["source"] for r in rs)), "months": sorted({r["read_on"] for r in rs}),
            "all_agree": all_agree, "disagree_by_field": {f: disagree.get(f, 0) for f in FIELDS}}


def sample(name: str, n: int = 12, only_disagree: bool = False) -> list[dict]:
    out = []
    for r in load(name):
        dis = [f for f in FIELDS if not agree(r, f)]
        if only_disagree and not dis:
            continue
        out.append({"doc_id": r["doc_id"], "kind": r["kind"], "issuer": r["issuer"], "source": r["source"], "words": len(r["words"]),
                    "parser": {f: r["parser"][f]["value"] for f in FIELDS}, "vision": r["vision"], "disagree": dis})
        if len(out) >= n:
            break
    return out
