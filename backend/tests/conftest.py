from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import dispose_engine
from app.main import app


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
def client(data_dir: Path) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
