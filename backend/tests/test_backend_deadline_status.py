"""A deadline read from a Clio task is served with that task's status, so a statute the
firm has met reads as met, not as passed (D40, critic Pass 4 finding 1)."""

from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Literal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Confidence, Fact, FactKind, Origin, Source, SourceType
from app.schemas import validate_payload
from app.services.matter_queries import matter_actions
from tests.fixtures.synthetic_matter import MATTER_ID


def _fact(
    session: Session, source: Source, kind: FactKind, value: dict[str, Any], on: date
) -> Fact:
    fact = Fact(
        matter_id=MATTER_ID,
        kind=kind,
        title="Statute of limitations",
        value_json=validate_payload(kind, value),
        event_date=on,
        source_id=source.id,
        quote="Statute of limitations",
        significance=90,
        confidence=Confidence.HIGH,
        origin=Origin.CODE,
    )
    session.add(fact)
    return fact


def _statute_task(
    session: Session, status: Literal["open", "complete"], due: date
) -> Fact:
    """A Clio statute task as the digest stores it: a task fact and a deadline fact
    from the same record, the deadline without the task's status."""
    due_at = datetime.combine(due, time(17, 0), UTC).isoformat()
    source = Source(
        matter_id=MATTER_ID,
        clio_type=SourceType.TASK,
        clio_id=f"statute-task-{session.query(Source).count()}",
        raw_json={"name": "Statute of limitations", "status": status},
    )
    session.add(source)
    session.flush()
    _fact(session, source, FactKind.TASK, {"status": status, "due_at": due_at}, due)
    deadline = _fact(
        session,
        source,
        FactKind.DEADLINE,
        {"deadline_type": "statute_of_limitations", "due_at": due_at},
        due,
    )
    session.commit()
    return deadline


def _deadlines(client: TestClient) -> dict[int, dict[str, Any]]:
    response = client.get(f"/api/matters/{MATTER_ID}/timeline?kind=deadline")
    assert response.status_code == 200, response.text
    return {row["id"]: row for row in response.json()}


def test_a_deadline_whose_task_is_complete_is_served_as_complete(
    seeded: Session, client: TestClient
) -> None:
    met = _statute_task(
        seeded, "complete", datetime.now(UTC).date() - timedelta(days=30)
    )

    assert _deadlines(client)[met.id]["value"]["status"] == "complete"
    source = client.get(f"/api/facts/{met.id}/source").json()
    assert source["fact"]["value"]["status"] == "complete"


def test_a_deadline_whose_task_is_open_is_served_as_open(
    seeded: Session, client: TestClient
) -> None:
    pending = _statute_task(
        seeded, "open", datetime.now(UTC).date() + timedelta(days=30)
    )

    assert _deadlines(client)[pending.id]["value"]["status"] == "open"


def test_a_deadline_with_no_task_has_no_status(
    seeded: Session, client: TestClient
) -> None:
    deadlines = _deadlines(client)

    # The synthetic matter's deadlines come from calendar entries.
    assert deadlines
    assert all(row["value"]["status"] is None for row in deadlines.values())


def test_a_met_deadline_is_not_upcoming(seeded: Session) -> None:
    today = datetime.now(UTC).date()
    met = _statute_task(seeded, "complete", today + timedelta(days=60))
    pending = _statute_task(seeded, "open", today + timedelta(days=60))

    upcoming = {f.id for f in matter_actions(seeded, MATTER_ID, today).upcoming}

    assert met.id not in upcoming
    assert pending.id in upcoming
