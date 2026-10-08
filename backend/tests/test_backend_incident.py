"""The header's date of incident cites a source that shows the date (critic finding 7)."""

from datetime import date, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Confidence, Fact, FactKind, Origin, Source, SourceType
from tests.fixtures.synthetic_matter import MATTER_ID


def _fields(session: Session) -> list[Fact]:
    """The synthetic matter's date-of-incident facts, mapped in code from Clio."""
    facts = list(
        session.scalars(
            select(Fact)
            .where(Fact.kind == FactKind.INCIDENT, Fact.origin == Origin.CODE)
            .order_by(Fact.significance.desc())
        )
    )
    assert facts and all(f.event_date is not None for f in facts)
    return facts


def _field(session: Session) -> Fact:
    """The field fact that decides the day: the most significant one."""
    return _fields(session)[0]


def _drop_fields(session: Session) -> date:
    """Remove the field facts, leaving the matter with model reads only; their day."""
    fields = _fields(session)
    day = fields[0].event_date
    assert day is not None
    for fact in fields:
        session.delete(fact)
    session.commit()
    return day


def _add(session: Session, on: date, quote: str, significance: int = 50) -> Fact:
    source = Source(
        matter_id=MATTER_ID,
        clio_type=SourceType.NOTE,
        clio_id=f"incident-note-{session.query(Source).count()}",
        raw_json={},
    )
    session.add(source)
    session.flush()
    fact = Fact(
        matter_id=MATTER_ID,
        kind=FactKind.INCIDENT,
        title="Collision",
        value_json={"description": "Collision"},
        event_date=on,
        source_id=source.id,
        quote=quote,
        significance=significance,
        confidence=Confidence.HIGH,
        origin=Origin.MODEL,
    )
    session.add(fact)
    session.commit()
    return fact


def _incident(client: TestClient) -> dict[str, Any]:
    response = client.get(f"/api/matters/{MATTER_ID}")
    assert response.status_code == 200, response.text
    incident = response.json()["incident"]
    assert incident is not None
    return incident


def _written(day: date) -> str:
    return f"{day:%B} {day.day}, {day.year}"


def test_the_clio_field_is_cited_over_a_more_significant_read(
    seeded: Session, client: TestClient
) -> None:
    field = _field(seeded)
    assert field.event_date is not None
    _add(seeded, field.event_date, "The other car struck the rear bumper.", 99)

    incident = _incident(client)

    assert incident["fact"]["id"] == field.id
    assert incident["on"] == field.event_date.isoformat()


def test_without_the_field_a_quote_that_shows_the_date_is_cited(
    seeded: Session, client: TestClient
) -> None:
    day = _drop_fields(seeded)
    _add(seeded, day, "The other car struck the rear bumper.", 99)
    showing = _add(seeded, day, f"Rear-ended on {_written(day)} at a light.", 40)

    assert _incident(client)["fact"]["id"] == showing.id


def test_without_the_field_the_date_most_records_state_wins(
    seeded: Session, client: TestClient
) -> None:
    day = _drop_fields(seeded)
    later = day + timedelta(days=3)
    _add(seeded, later, f"Collision on {_written(later)}.", 99)
    agreeing = [_add(seeded, day, f"Collision on {_written(day)}.") for _ in range(2)]

    incident = _incident(client)

    assert incident["on"] == day.isoformat()
    assert incident["fact"]["id"] in {f.id for f in agreeing}
