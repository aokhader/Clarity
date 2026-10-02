from pathlib import Path

from fastapi.testclient import TestClient


def test_startup_creates_database_and_health_answers(
    client: TestClient, data_dir: Path
) -> None:
    response = client.get("/api/ops/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert (data_dir / "app.db").exists()
