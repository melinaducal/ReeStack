"""Database engine and session management for Reesatck."""
import os
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy import event

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _default_database_url() -> str:
    raw = os.getenv("DATABASE_URL", "").strip()
    if raw:
        return raw
    return f"sqlite:///{BACKEND_DIR / 'reesatck.db'}"


DATABASE_URL = _default_database_url()

is_sqlite = DATABASE_URL.startswith("sqlite")
engine_kwargs = {"echo": False, "future": True}
if is_sqlite:
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)

if is_sqlite:

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_session():
    with Session(engine) as session:
        yield session


def init_db() -> None:
    from . import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
