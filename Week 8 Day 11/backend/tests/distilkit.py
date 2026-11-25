"""Helpers the Day 11 tests share: small reads to label, and one small model trained once per test session."""

import json
from functools import lru_cache

from app.prototype.models import FIELDS, OcrWord


def read(**override) -> dict:
    """A tiny read: "Mr Ali Khan, 3 Spa Road GL5 1AB, Statement date 06 Oct 2026, Northmere Bank", both readings agreeing."""
    words = [["w001", "Northmere", 0.1, 0.05, 0.3, 0.07, 1.0], ["w002", "Bank", 0.31, 0.05, 0.4, 0.07, 1.0],
             ["w003", "Mr", 0.1, 0.2, 0.13, 0.22, 1.0], ["w004", "Ali", 0.14, 0.2, 0.18, 0.22, 1.0], ["w005", "Khan", 0.19, 0.2, 0.24, 0.22, 1.0],
             ["w006", "3", 0.1, 0.23, 0.11, 0.25, 1.0], ["w007", "Spa", 0.12, 0.23, 0.16, 0.25, 1.0], ["w008", "Road", 0.17, 0.23, 0.22, 0.25, 1.0],
             ["w009", "GL5", 0.1, 0.26, 0.13, 0.28, 1.0], ["w010", "1AB", 0.14, 0.26, 0.18, 0.28, 1.0],
             ["w011", "Statement", 0.6, 0.2, 0.7, 0.22, 1.0], ["w012", "date", 0.71, 0.2, 0.75, 0.22, 1.0],
             ["w013", "06", 0.76, 0.2, 0.78, 0.22, 1.0], ["w014", "Oct", 0.79, 0.2, 0.82, 0.22, 1.0], ["w015", "2026", 0.83, 0.2, 0.87, 0.22, 1.0]]
    parser = {"full_name": {"value": "Mr Ali Khan", "word_ids": ["w003", "w004", "w005"]},
              "address": {"value": "3 Spa Road GL5 1AB", "word_ids": ["w006", "w007", "w008", "w009", "w010"]},
              "statement_date": {"value": "06 Oct 2026", "word_ids": ["w013", "w014", "w015"]},
              "issuer": {"value": "Northmere Bank", "word_ids": ["w001", "w002"]}}
    r = {"doc_id": "P-TEST", "kind": "bank_statement", "issuer": "Northmere Bank", "source": "text_layer", "read_on": "2026-11",
         "words": words, "parser": parser, "vision": {f: parser[f]["value"] for f in FIELDS}}
    r = json.loads(json.dumps(r))
    for k, v in override.items():
        r[k] = v
    return r


def ocr_words(*texts_conf) -> list[OcrWord]:
    return [OcrWord(id=f"w{i + 1:03d}", text=t, box=[0.1 * i, 0.1, 0.1 * i + 0.08, 0.12], confidence=c) for i, (t, c) in enumerate(texts_conf)]


@lru_cache(maxsize=1)
def trained() -> str:
    """Train the small model once on the pilot's reads (with your word_labels()), and return its name."""
    from app.distil import service
    from app.distil.reads import load
    from app.distil.model import train
    train("kit", load("pilot"), ["pilot"])
    service.set_active("kit")
    return "kit"
