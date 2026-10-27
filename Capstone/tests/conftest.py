"""Every test runs with fake models and a temporary database, set before the app is imported."""
import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="hiring_tests_"))
os.environ["FAKE_MODELS"] = "1"
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["STORAGE_DIR"] = str(_TMP / "storage")
os.environ["SECRET_KEY"] = "test-secret-key-for-sessions-only"
os.environ["OPENROUTER_API_KEY"] = ""

import pytest  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
KIT = ROOT / "starter_kit"
CVS = KIT / "cvs" / "cloud_support_engineer"
VOICE = KIT / "voice_notes"


@pytest.fixture(autouse=True)
def fresh_db():
    from app import models  # noqa: F401
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()
