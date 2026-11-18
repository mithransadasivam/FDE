"""The document sets the pipeline knows, and the bank's double-keyed answers for each one.

A set is a folder of documents, a manifest (one row per document) and the keyed answers. The October batch is built in.
To add a set (the homework), list it in engagement/pipeline_sets.json: the console reads that file when it exists.
"""

import csv
from functools import lru_cache
from pathlib import Path

from app import store
from app.config import REPO

DEFAULT_SETS = [{
    "name": "october",
    "label": "October batch: 200 bills and bank statements",
    "documents": "data/Day06_Slide10_documents",
    "manifest": "data/Day06_Slide10_manifest.csv",
    "keyed": "data/Day06_Slide10_double_keyed.csv",
}]


def sets() -> list[dict]:
    return store.load("pipeline_sets.json", DEFAULT_SETS)


def get_set(name: str) -> dict:
    for s in sets():
        if s["name"] == name:
            return s
    raise KeyError(f"No document set called {name!r}: see engagement/pipeline_sets.json")


@lru_cache(maxsize=16)
def _read_csv(path: str, _mtime: float) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_csv(path: Path) -> list[dict]:
    return _read_csv(str(path), path.stat().st_mtime)


def manifest(set_name: str) -> list[dict]:
    """One row per document: doc_id, file, kind, issuer, received, slices (separated by ';')."""
    return read_csv(REPO / get_set(set_name)["manifest"])


def _where(doc_id: str) -> tuple[dict, dict]:
    for s in sets():
        for row in manifest(s["name"]):
            if row["doc_id"] == doc_id:
                return s, row
    raise KeyError(f"No document {doc_id!r} in any set")


def set_of(doc_id: str) -> str:
    return _where(doc_id)[0]["name"]


def doc_row(doc_id: str) -> dict:
    return _where(doc_id)[1]


def document_file(doc_id: str) -> Path:
    """The file the bank sent: …/B-001.pdf or …/B-061.jpg."""
    s, row = _where(doc_id)
    return REPO / s["documents"] / row["file"]


def ocr_file(doc_id: str) -> Path:
    s, _ = _where(doc_id)
    return REPO / s["documents"] / f"{doc_id}.ocr.json"


def page_image(doc_id: str) -> Path:
    """A picture of the page, for the screen and for the vision model: the JPG itself, or <doc_id>.page.jpg for a PDF."""
    f = document_file(doc_id)
    return f if f.suffix.lower() == ".jpg" else f.with_name(f"{doc_id}.page.jpg")


def keyed(set_name: str) -> list[dict]:
    """One row per document and field: what keyer A and keyer B typed, the label, and how it was settled."""
    return read_csv(REPO / get_set(set_name)["keyed"])


def labels(set_name: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for r in keyed(set_name):
        out.setdefault(r["doc_id"], {})[r["field"]] = r["label"]
    return out


def slices(set_name: str) -> dict[str, list[str]]:
    return {r["doc_id"]: [s for s in r["slices"].split(";") if s] for r in manifest(set_name)}
