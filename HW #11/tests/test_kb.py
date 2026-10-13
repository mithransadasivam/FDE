from app.kb import overview, rebuild


def fake_embed(texts):
    return [[float(len(t)), 1.0, 0.5] for t in texts]


def make_docs(folder):
    folder.mkdir()
    (folder / "a.md").write_text("alpha " * 200, encoding="utf-8")
    (folder / "empty.txt").write_text("   ", encoding="utf-8")
    return folder


def test_missing_index_state(tmp_path):
    info = overview(make_docs(tmp_path / "docs"), tmp_path / "db")
    assert info["state"] == "missing" and info["documents"] == 2 and info["readable"] == 1
    assert {r["Document"]: r["Status"] for r in info["rows"]}["a.md"] == "Not indexed"


def test_rebuild_makes_index_ready_and_flags_empty_document(tmp_path):
    docs = make_docs(tmp_path / "docs")
    count = rebuild(docs, tmp_path / "db", fake_embed)
    info = overview(docs, tmp_path / "db")
    assert info["state"] == "ready" and info["indexed_chunks"] == count == info["chunks"]
    statuses = {r["Document"]: r["Status"] for r in info["rows"]}
    assert statuses["a.md"] == "Indexed" and "no readable text" in statuses["empty.txt"]


def test_changed_documents_make_index_out_of_date(tmp_path):
    docs = make_docs(tmp_path / "docs")
    rebuild(docs, tmp_path / "db", fake_embed)
    (docs / "b.md").write_text("beta " * 200, encoding="utf-8")
    assert overview(docs, tmp_path / "db")["state"] == "out of date"
