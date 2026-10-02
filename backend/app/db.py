"""Engine, sessions, and table creation for the SQLite store.

There are no migrations: tables are created at startup, and `cli reset` drops
everything. The engine is built lazily so tests can point DATA_DIR elsewhere first.
"""

import sqlite3
from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry

from app.config import get_settings
from app.models import Base
from app.services.users import seed_firm_users


def _configure_sqlite(
    connection: sqlite3.Connection, _record: ConnectionPoolEntry
) -> None:
    cursor = connection.cursor()
    # WAL lets the API keep reading while a CLI sync or digest writes.
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    # FastAPI runs sync handlers in a thread pool; each request still gets its own session.
    engine = create_engine(
        settings.database_url, connect_args={"check_same_thread": False}
    )
    event.listen(engine, "connect", _configure_sqlite)
    return engine


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def init_db() -> None:
    settings = get_settings()
    for directory in (settings.data_dir, settings.files_dir, settings.pages_dir):
        directory.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(get_engine())
    # Stub firm users (no real authentication), so sharing and visits work from the start.
    with get_sessionmaker()() as session:
        seed_firm_users(session)
        session.commit()


def dispose_engine() -> None:
    """Close pooled connections and forget the engine, so the database file can be removed."""
    if get_engine.cache_info().currsize:
        get_engine().dispose()
    get_sessionmaker.cache_clear()
    get_engine.cache_clear()


def check_database(session: Session) -> None:
    """Raise if the database cannot answer a trivial query."""
    session.execute(text("SELECT 1"))


def get_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request."""
    with get_sessionmaker()() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
