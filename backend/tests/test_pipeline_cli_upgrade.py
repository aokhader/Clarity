"""`cli upgrade-schema` and `cli seed-dev` on a database made before a new fact kind.

SQLite stores an enum as a CHECK constraint, so a database created before a kind was
added refuses that kind until `upgrade_schema()` rebuilds the table. The command backs
the database up first; seed-dev upgrades its development database on its own.
"""

import sqlite3
from pathlib import Path

import pytest

from app.cli import main
from app.config import get_settings
from app.db import dispose_engine, init_db
from app.models import FactKind

NEW_KINDS = (FactKind.LITIGATION_EVENT, FactKind.ECONOMIC_DAMAGES)


def _connect(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(path, isolation_level=None)


def _facts_sql(connection: sqlite3.Connection) -> str:
    return connection.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'facts'"
    ).fetchone()[0]


def _old_database() -> Path:
    """A database whose facts table was created before NEW_KINDS existed."""
    init_db()
    dispose_engine()
    path = get_settings().database_path
    connection = _connect(path)
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
    connection.execute("PRAGMA foreign_keys=OFF")
    connection.execute("DROP TABLE facts")
    connection.execute(old_sql)
    for sql in indexes:
        connection.execute(sql)
    connection.close()
    return path


def _backups() -> list[Path]:
    return sorted(get_settings().backups_dir.glob("app-*-pre-upgrade*.db"))


def test_upgrade_backs_up_then_rebuilds_a_table_with_an_old_constraint(
    data_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _old_database()

    assert main(["upgrade-schema"]) == 0

    out = capsys.readouterr().out
    assert "Rebuilt with the current constraints: facts" in out
    [backup] = _backups()
    copy = sqlite3.connect(f"file:{backup.as_posix()}?mode=ro", uri=True)
    assert copy.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    # Taken before the rebuild: the copy still has the old constraint.
    assert FactKind.LITIGATION_EVENT.value not in _facts_sql(copy)
    copy.close()
    live = _connect(path)
    assert all(kind.value in _facts_sql(live) for kind in NEW_KINDS)
    live.close()


def test_a_second_upgrade_finds_nothing_to_do(
    data_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _old_database()
    main(["upgrade-schema"])
    capsys.readouterr()

    assert main(["upgrade-schema"]) == 0

    assert "Nothing to upgrade" in capsys.readouterr().out
    assert len(_backups()) == 2


def test_upgrade_without_a_database_creates_nothing(
    data_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["upgrade-schema"]) == 0

    assert "no database" in capsys.readouterr().out
    assert not get_settings().database_path.exists()
    assert _backups() == []


def test_seed_dev_upgrades_an_old_database_and_seeds_the_new_kinds(
    data_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _old_database()

    assert main(["seed-dev"]) == 0

    assert "rebuilt facts" in capsys.readouterr().out
    connection = _connect(path)
    seeded = connection.execute(
        "SELECT count(*) FROM facts WHERE kind = ?", (FactKind.LITIGATION_EVENT.value,)
    ).fetchone()[0]
    connection.close()
    assert seeded > 0
