from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.ai.voice import transcribe
from app.config import get_settings
from app.main import app
from app.models import DecisionLog, Requisition
from scripts.create_users import DEMO_PASSWORD, create_users
from tests.conftest import VOICE

WAV = VOICE / "REQ_cloud_support_engineer.wav"


@pytest.fixture
def hm(db):
    create_users(db)
    with TestClient(app, follow_redirects=False) as c:
        c.post("/login", data={"email": "hm@example.com", "password": DEMO_PASSWORD})
        yield c


def upload(client, name="REQ_cloud_support_engineer.wav", data=None, title="Cloud Support Engineer"):
    data = WAV.read_bytes() if data is None else data
    return client.post("/requisitions", data={"title": title}, files={"audio": (name, data, "audio/wav")})


def test_upload_saves_with_random_name_logs_and_transcribes(hm, db):
    r = upload(hm)
    assert r.status_code == 303
    req = db.get(Requisition, 1)
    assert req.audio_name == "REQ_cloud_support_engineer.wav"
    assert "REQ_cloud" not in Path(req.audio_path).name and Path(req.audio_path).suffix == ".wav"
    assert Path(req.audio_path).parent == get_settings().storage_dir / "audio"
    assert req.status == "TRANSCRIBED" and "young and energetic" in req.transcript
    actions = [e.action for e in db.query(DecisionLog).order_by(DecisionLog.id)]
    assert actions[:2] == ["requisition created", "transcribed"]


def test_detail_page_has_player_and_transcript_and_audio_streams(hm):
    upload(hm)
    html = hm.get("/requisitions/1").text
    assert "<audio" in html and "native English speaker" in html
    a = hm.get("/requisitions/1/audio")
    assert a.status_code == 200 and a.headers["content-type"] == "audio/wav" and len(a.content) > 1000


def test_txt_file_is_refused_with_a_clear_message(hm, db):
    r = upload(hm, name="notes.txt", data=b"hello")
    assert r.status_code == 400 and "File type .txt is not accepted" in r.text
    assert db.query(Requisition).count() == 0


def test_empty_file_refused(hm):
    assert "The file is empty" in upload(hm, data=b"").text


def test_path_trick_in_filename_never_touches_disk_name(hm, db):
    upload(hm, name="../evil.wav", data=WAV.read_bytes())
    req = db.get(Requisition, 1)
    assert ".." not in req.audio_path and "evil" not in Path(req.audio_path).name


def test_too_big_file_refused(hm):
    assert "larger than 25 MB" in upload(hm, data=b"0" * (25 * 1024 * 1024 + 1)).text


def test_recruiter_can_view_but_not_create(db, hm):
    upload(hm)
    with TestClient(app, follow_redirects=False) as rc:
        rc.post("/login", data={"email": "recruiter@example.com", "password": DEMO_PASSWORD})
        assert rc.get("/requisitions/new").status_code == 403
        assert upload(rc).status_code == 403
        assert rc.get("/requisitions").status_code == 200 and rc.get("/requisitions/1").status_code == 200


def test_fake_transcribe_reads_sidecar_file_by_original_name(tmp_path):
    f = tmp_path / "random123.wav"
    f.write_bytes(b"x")
    assert "Data Analyst" in transcribe(f, "REQ_data_analyst.wav")
    with pytest.raises(FileNotFoundError):
        transcribe(f, "unknown.wav")


def test_failed_transcription_is_shown_on_the_page(hm, db):
    upload(hm, name="unknown_note.wav")
    req = db.get(Requisition, 1)
    assert req.status == "ERROR" and "Transcription failed" in req.error
    assert "Transcription failed" in hm.get("/requisitions/1").text
