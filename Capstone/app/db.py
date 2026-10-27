"""SQLAlchemy 2 on SQLite (Prompt 2)."""
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_url = get_settings().database_url
if _url.startswith("sqlite:///"):
    Path(_url.replace("sqlite:///", "", 1)).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(_url, connect_args={"check_same_thread": False, "timeout": 30} if _url.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_db():
    """FastAPI dependency: one session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401  (registers the tables)
    Base.metadata.create_all(engine)
    init_ops_db()


# ---- the ops database: prompt log, cost ledger and traces live apart from the business data, so writing them never
# waits for (or locks) a request that is in the middle of saving a candidate ----------------------------------------------
class OpsBase(DeclarativeBase):
    pass


_ops_url = get_settings().ops_database_url
if _ops_url.startswith("sqlite:///"):
    Path(_ops_url.replace("sqlite:///", "", 1)).parent.mkdir(parents=True, exist_ok=True)
ops_engine = create_engine(_ops_url, connect_args={"check_same_thread": False, "timeout": 30} if _ops_url.startswith("sqlite") else {})
OpsSession = sessionmaker(bind=ops_engine, expire_on_commit=False)


def _wal(dbapi_conn, _record):
    try:
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
    except Exception:
        pass


# WAL only for the ops database (many small writes). The business database keeps the default journal: with WAL, a session that
# holds an old read snapshot cannot upgrade to a write.
if _ops_url.startswith("sqlite"):
    event.listen(ops_engine, "connect", _wal)


def init_ops_db() -> None:
    from app import models_ext  # noqa: F401
    OpsBase.metadata.create_all(ops_engine)
