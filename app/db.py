"""SQLAlchemy 2 on SQLite (Prompt 2)."""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_url = get_settings().database_url
if _url.startswith("sqlite:///"):
    Path(_url.replace("sqlite:///", "", 1)).parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(_url, connect_args={"check_same_thread": False} if _url.startswith("sqlite") else {})
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
