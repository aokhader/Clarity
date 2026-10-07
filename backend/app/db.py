"""Engine, sessions, table creation, and in-place schema upgrades for the SQLite store.

Tables are created at startup, and `cli reset` drops everything. There is no migration
framework; `upgrade_schema` covers the one change the store needs in place (D24): an
enum that gained values. The engine is built lazily so tests can point DATA_DIR
elsewhere first.
"""

import logging
import re
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine, Enum, Table, create_engine, event, text
from sqlalchemy.dialects import sqlite as sqlite_dialect
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry
from sqlalchemy.schema import CreateIndex, CreateTable

from app.config import get_settings
from app.models import Base
from app.services.users import seed_firm_users

log = logging.getLogger(__name__)


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


# --- In-place schema upgrade (D24) --------------------------------------------------

# An enum column's stored constraint, as SQLAlchemy writes it: CHECK (kind IN ('a', 'b')).
_ENUM_CHECK = re.compile(
    r"CHECK\s*\(\s*\"?(?P<column>\w+)\"?\s+IN\s*\((?P<values>[^)]*)\)\s*\)",
    re.IGNORECASE,
)
_DIALECT = sqlite_dialect.dialect()


class SchemaUpgradeFailed(Exception):
    """The rebuild would lose rows or break a foreign key; nothing was changed."""


def upgrade_schema() -> list[str]:
    """Rebuild each table whose enum CHECK constraint lacks values the code now has.

    SQLite cannot alter a constraint, so a table whose enum gained values (a new fact
    kind, a new source type) would refuse them. Following SQLite's rebuild recipe, in
    one transaction: create the table anew from the model, copy every row, drop the old
    one, rename the new one, recreate its indexes, then check foreign keys. The database
    is backed up first, next to itself. A second run finds nothing to do. Stop the API
    and any CLI job before running it. Returns the tables rebuilt.
    """
    path = Path(get_engine().url.database or "")
    connection = sqlite3.connect(path, isolation_level=None)
    try:
        stale = [
            t for t in Base.metadata.sorted_tables if _lacks_enum_values(connection, t)
        ]
        if not stale:
            return []
        backup = _backup(connection, path)
        log.info(
            "Backed up %s to %s before upgrading %d tables", path, backup, len(stale)
        )
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("BEGIN IMMEDIATE")
        try:
            for table in stale:
                _rebuild(connection, table)
            if connection.execute("PRAGMA foreign_key_check").fetchall():
                raise SchemaUpgradeFailed("the rebuilt tables break a foreign key")
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise
        finally:
            connection.execute("PRAGMA foreign_keys=ON")
    finally:
        connection.close()
    return [t.name for t in stale]


def _stored_sql(connection: sqlite3.Connection, name: str) -> str | None:
    row = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone()
    return row[0] if row else None


def _lacks_enum_values(connection: sqlite3.Connection, table: Table) -> bool:
    stored = _stored_sql(connection, table.name)
    if stored is None:
        return False  # not created yet: create_all writes the current constraint
    allowed = {
        match["column"]: {v.strip().strip("'") for v in match["values"].split(",")}
        for match in _ENUM_CHECK.finditer(stored)
    }
    return any(
        isinstance(column.type, Enum)
        and column.name in allowed
        and not set(column.type.enums) <= allowed[column.name]
        for column in table.columns
    )


def _backup(connection: sqlite3.Connection, path: Path) -> Path:
    """A consistent copy through SQLite's backup API, which includes the WAL's pages."""
    target = path.with_name(f"{path.name}.bak-{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}")
    copy = sqlite3.connect(target)
    try:
        connection.backup(copy)
    finally:
        copy.close()
    return target


def _rebuild(connection: sqlite3.Connection, table: Table) -> None:
    name = _DIALECT.identifier_preparer.format_table(table)
    staging = f"{table.name}__upgrade"
    existing = [row[1] for row in connection.execute(f"PRAGMA table_info({name})")]
    dropped = set(existing) - {c.name for c in table.columns}
    if dropped:
        raise SchemaUpgradeFailed(
            f"{table.name} has columns the model lacks: {dropped}"
        )
    create = str(CreateTable(table).compile(dialect=_DIALECT))
    connection.execute(
        create.replace(f"CREATE TABLE {name} ", f"CREATE TABLE {staging} ", 1)
    )
    columns = ", ".join(_DIALECT.identifier_preparer.quote(c) for c in existing)
    connection.execute(
        f"INSERT INTO {staging} ({columns}) SELECT {columns} FROM {name}"
    )
    before = connection.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
    after = connection.execute(f"SELECT count(*) FROM {staging}").fetchone()[0]
    if before != after:
        raise SchemaUpgradeFailed(f"{table.name}: {before} rows became {after}")
    connection.execute(f"DROP TABLE {name}")
    connection.execute(f"ALTER TABLE {staging} RENAME TO {name}")
    for index in table.indexes:
        connection.execute(str(CreateIndex(index).compile(dialect=_DIALECT)))
    log.info("Rebuilt %s with its current constraints: %d rows kept", table.name, after)
