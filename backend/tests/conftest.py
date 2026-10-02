from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import dispose_engine, get_sessionmaker, init_db
from app.main import app
from tests.fixtures.synthetic_matter import load_synthetic_matter


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Point the app at a throwaway data directory for the length of one test."""
    path = tmp_path / "data"
    monkeypatch.setenv("DATA_DIR", str(path))
    get_settings.cache_clear()
    dispose_engine()
    yield path
    dispose_engine()
    get_settings.cache_clear()


@pytest.fixture
def session(data_dir: Path) -> Iterator[Session]:
    init_db()
    with get_sessionmaker()() as db_session:
        yield db_session


@pytest.fixture
def seeded(session: Session) -> Session:
    """A session over a database holding the synthetic matter."""
    load_synthetic_matter(session)
    session.commit()
    return session


@pytest.fixture
def client(data_dir: Path) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
