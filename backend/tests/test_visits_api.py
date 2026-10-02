"""Stub users and the "since you last opened" block."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.fixtures.synthetic_matter import MATTER_ID


def _user_id(client: TestClient, role: str) -> int:
    users = client.get("/api/users").json()
    return next(u["id"] for u in users if u["role"] == role)


def _changes(client: TestClient, user_id: int) -> dict:
    response = client.get(
        f"/api/matters/{MATTER_ID}/changes", headers={"X-User-Id": str(user_id)}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_stub_users_are_seeded_at_startup(client: TestClient) -> None:
    roles = {u["role"] for u in client.get("/api/users").json()}
    assert roles == {"attorney", "paralegal", "case manager"}


def test_changes_need_a_firm_user(seeded: Session, client: TestClient) -> None:
    assert client.get(f"/api/matters/{MATTER_ID}/changes").status_code == 401
    unknown = {"X-User-Id": "999"}
    assert (
        client.get(f"/api/matters/{MATTER_ID}/changes", headers=unknown).status_code
        == 401
    )


def test_changes_are_facts_from_records_newer_than_the_last_visit(
    seeded: Session, client: TestClient
) -> None:
    attorney = _changes(client, _user_id(client, "attorney"))  # seeded 21 days ago
    paralegal = _changes(client, _user_id(client, "paralegal"))  # seeded 7 days ago

    opened = datetime.fromisoformat(attorney["last_opened_at"])
    assert abs(datetime.now(UTC) - timedelta(days=21) - opened) < timedelta(minutes=1)
    attorney_titles = {f["title"] for f in attorney["facts"]}
    paralegal_titles = {f["title"] for f in paralegal["facts"]}
    # The offer arrived 6 days ago, the client's email 12 days ago, the intake note
    # long before either visit.
    assert "Insurer offered $40,000" in attorney_titles & paralegal_titles
    assert "Client emailed for an update" in attorney_titles - paralegal_titles
    assert "Police report faults other driver" not in attorney_titles


def test_a_user_who_never_opened_the_matter_sees_no_list(
    seeded: Session, client: TestClient
) -> None:
    changes = _changes(client, _user_id(client, "case manager"))
    assert changes == {"last_opened_at": None, "facts": []}


def test_recording_a_visit_clears_the_changes(
    seeded: Session, client: TestClient
) -> None:
    attorney = _user_id(client, "attorney")
    assert _changes(client, attorney)["facts"]
    response = client.post(
        f"/api/matters/{MATTER_ID}/opened", headers={"X-User-Id": str(attorney)}
    )
    assert response.status_code == 200
    after = _changes(client, attorney)
    assert after["facts"] == []
    assert after["last_opened_at"] == response.json()["last_opened_at"]
