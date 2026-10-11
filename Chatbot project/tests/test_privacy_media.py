"""Pictures, recordings and what was said are never written to disk or to the log by the app. A static check, so a new line that does it fails."""
import re
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"


def test_only_the_document_upload_writes_file_bytes():
    offenders = [f.name for f in APP.glob("*.py") if f.name != "uploads.py" and re.search(r"write_bytes\(|open\([^)]*[\"']wb[\"']", f.read_text(encoding="utf-8"))]
    assert offenders == []  # uploads.py saves a document the person chose to add to the knowledge base; nothing else saves bytes


def test_every_picture_save_goes_to_memory_not_to_a_file():
    for f in APP.glob("*.py"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if ".save(" in line:
                assert re.search(r"\.save\(out\b", line), f"{f.name}: {line.strip()} (a picture must be saved to an in-memory buffer)"


def test_the_call_log_records_only_numbers_and_names_of_kinds():
    from app.calllog import log_call, read_log
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "calls.jsonl"
        from app.voice import transcribe
        from tests.test_voice import Speech, wav
        import app.voice as voice
        original = voice.log_call
        voice.log_call = lambda entry: log_call(entry, path)
        try:
            transcribe(wav(1.0), Speech("a private spoken sentence"))
        finally:
            voice.log_call = original
        text = path.read_text(encoding="utf-8")
        assert "private" not in text and all(isinstance(v, (int, float, str)) for v in read_log(path)[0].values()) and len(text) < 300
