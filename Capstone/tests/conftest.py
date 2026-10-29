"""Every test runs with fake models and a temporary database, set before the app is imported."""
import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="hiring_tests_"))
os.environ["FAKE_MODELS"] = "1"
os.environ["ENABLE_INTEGRATIONS"] = "1"  # the API and webhooks are off by default; the tests that cover them switch them on
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["STORAGE_DIR"] = str(_TMP / "storage")
os.environ["OPS_DATABASE_URL"] = f"sqlite:///{(_TMP / 'ops.db').as_posix()}"
os.environ["SECRET_KEY"] = "test-secret-key-for-sessions-only"
os.environ["OPENROUTER_API_KEY"] = ""

import pytest  # noqa: E402

from app.db import Base, OpsBase, SessionLocal, engine, ops_engine  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "starter_kit"
CVS = KIT / "cvs" / "cloud_support_engineer"
VOICE = KIT / "voice_notes"


@pytest.fixture(autouse=True)
def fresh_db():
    from app import models  # noqa: F401
    from app.ai.llm import clear_cache
    clear_cache()
    from app import branding
    branding.clear_cache()
    import shutil
    shutil.rmtree(_TMP / "storage" / "interviews", ignore_errors=True)  # interview audio from an earlier test must not leak into this one
    for folder in ("outbox_sent", "inbox", "practice"):  # sent emails, received replies and practice interviews of an earlier test must not leak either
        shutil.rmtree(_TMP / "storage" / folder, ignore_errors=True)
    from app.supervisor_graph import reset_checkpoints
    reset_checkpoints()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    OpsBase.metadata.drop_all(ops_engine)
    OpsBase.metadata.create_all(ops_engine)
    yield


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


class Platform:
    """A running app for one test: clients for each role, a published job, and helpers to apply with CVs."""

    def __init__(self, hm, rc, visitor):
        self.hm, self.rc, self.visitor = hm, rc, visitor

    def apply(self, name: str, folder: str = "cloud_support_engineer", job: int = 1):
        path = KIT / "cvs" / folder / name
        return self.visitor.post(f"/jobs/{job}/apply", data={"consent": "yes"}, files={"cv": (name, path.read_bytes(), "application/octet-stream")})

    def publish(self, note: str, title: str, req_id: int):
        self.hm.post("/requisitions", data={"title": title}, files={"audio": (f"REQ_{note}.wav", (VOICE / f"REQ_{note}.wav").read_bytes(), "audio/wav")})
        self.hm.post(f"/requisitions/{req_id}/generate")
        self.hm.post(f"/requisitions/{req_id}/approve", data={"comment": "ok"})
        self.hm.post(f"/requisitions/{req_id}/publish")


@pytest.fixture
def platform(db):
    from fastapi.testclient import TestClient

    from app.main import app
    from scripts.create_users import DEMO_PASSWORD, create_users

    create_users(db)
    clients = [TestClient(app, follow_redirects=False) for _ in range(3)]
    for c in clients:
        c.__enter__()
    hm, rc, visitor = clients
    hm.post("/login", data={"email": "hm@example.com", "password": DEMO_PASSWORD})
    rc.post("/login", data={"email": "recruiter@example.com", "password": DEMO_PASSWORD})
    p = Platform(hm, rc, visitor)
    p.publish("cloud_support_engineer", "Cloud Support Engineer", 1)
    yield p
    for c in clients:
        c.__exit__(None, None, None)
