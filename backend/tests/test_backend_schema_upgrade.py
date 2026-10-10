"""upgrade_schema rebuilds a table whose enum CHECK constraint is out of date (D24).

The test database is built as the real one was before D21: the synthetic matter, with
`facts.kind` allowing only the kinds the code had then. The kinds added since (D21,
D41) are all checked.
"""

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.db import get_engine, upgrade_schema
from app.models import FactKind
from tests.fixtures.synthetic_matter import load_synthetic_matter

NEW_KINDS = (
    FactKind.ECONOMIC_DAMAGES,
    FactKind.RECOVERY_CAP,
    FactKind.LITIGATION_EVENT,
)


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(Path(get_engine().url.database or ""), isolation_level=None)


def _facts_sql(connection: sqlite3.Connection) -> str:
    return connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'facts'"
    ).fetchone()[0]


def _counts(connection: sqlite3.Connection) -> dict[str, int]:
    tables = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    return {
        t: connection.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in tables
    }


def _indexes(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'facts'"
        )
    }


def _insert_new_kind(
    connection: sqlite3.Connection, kind: FactKind = FactKind.ECONOMIC_DAMAGES
) -> None:
    source_id = connection.execute("SELECT min(id) FROM sources").fetchone()[0]
    connection.execute(
        "INSERT INTO facts (matter_id, kind, title, value_json, source_id,"
        " mentions_strategy, visibility, significance, confidence, verified, origin,"
        " created_at) VALUES (1, ?, 'New kind', '{}', ?, 0, 'internal', 50, 'high', 1,"
        " 'model', '2031-07-14 00:00:00')",
        (kind.value, source_id),
    )


@pytest.fixture
def old_database(session: Session) -> Path:
    """The synthetic matter in a database whose facts.kind predates the new kinds."""
    load_synthetic_matter(session)
    session.commit()
    session.close()
    connection = _connect()
    marks = ", ".join("?" for _ in NEW_KINDS)
    connection.execute(
        f"DELETE FROM facts WHERE kind IN ({marks})", tuple(k.value for k in NEW_KINDS)
    )
    old_sql = _facts_sql(connection)
    for kind in NEW_KINDS:
        old_sql = old_sql.replace(f"'{kind.value}', ", "")
    assert all(kind.value not in old_sql for kind in NEW_KINDS)
    indexes = [
        row[0]
        for row in connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'index' AND tbl_name = 'facts'"
            " AND sql IS NOT NULL"
        )
    ]
    # SQLite's rebuild recipe, run backwards: the table as it was.
    connection.execute("PRAGMA foreign_keys=OFF")
    connection.execute("BEGIN")
    connection.execute(
        old_sql.replace("CREATE TABLE facts", "CREATE TABLE facts_old", 1)
    )
    connection.execute("INSERT INTO facts_old SELECT * FROM facts")
    connection.execute("DROP TABLE facts")
    connection.execute("ALTER TABLE facts_old RENAME TO facts")
    for sql in indexes:
        connection.execute(sql)
    connection.execute("COMMIT")
    connection.close()
    return Path(get_engine().url.database or "")


@pytest.mark.parametrize("kind", NEW_KINDS)
def test_the_old_constraint_refuses_the_new_kinds(
    old_database: Path, kind: FactKind
) -> None:
    connection = _connect()
    with pytest.raises(sqlite3.IntegrityError):
        _insert_new_kind(connection, kind)
    connection.close()


def test_the_upgrade_keeps_every_row_and_accepts_the_new_kinds(
    old_database: Path,
) -> None:
    connection = _connect()
    counts = _counts(connection)
    fact_ids = [r[0] for r in connection.execute("SELECT id FROM facts ORDER BY id")]
    indexes = _indexes(connection)
    connection.close()

    assert upgrade_schema() == ["facts"]

    connection = _connect()
    assert _counts(connection) == counts
    assert [
        r[0] for r in connection.execute("SELECT id FROM facts ORDER BY id")
    ] == fact_ids
    assert _indexes(connection) == indexes
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    for kind in NEW_KINDS:
        _insert_new_kind(connection, kind)
    connection.close()


def test_the_database_is_backed_up_before_the_upgrade(old_database: Path) -> None:
    upgrade_schema()

    [backup] = old_database.parent.glob(f"{old_database.name}.bak-*")
    copy = sqlite3.connect(backup)
    # The backup is the database as it was: the old constraint, every fact.
    assert FactKind.ECONOMIC_DAMAGES.value not in _facts_sql(copy)
    assert copy.execute("SELECT count(*) FROM facts").fetchone()[0] > 0
    copy.close()


def test_a_second_run_changes_nothing(old_database: Path) -> None:
    upgrade_schema()
    connection = _connect()
    sql, counts = _facts_sql(connection), _counts(connection)
    connection.close()

    assert upgrade_schema() == []

    connection = _connect()
    assert (_facts_sql(connection), _counts(connection)) == (sql, counts)
    connection.close()
    assert len(list(old_database.parent.glob(f"{old_database.name}.bak-*"))) == 1


def test_a_current_database_needs_nothing(session: Session) -> None:
    assert upgrade_schema() == []
