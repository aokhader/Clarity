"""The header's account of the incident comes from a record the model read on the
incident day, never from the date-of-incident field, whose title is a label (D39)."""

from datetime import date, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Confidence, Fact, FactKind, Origin, Source, SourceType
from app.schemas import validate_payload
from app.services.incident import incident_account
from tests.fixtures.synthetic_matter import MATTER_ID


def _fields(session: Session) -> list[Fact]:
    facts = list(
        session.scalars(
            select(Fact).where(
                Fact.kind == FactKind.INCIDENT, Fact.origin == Origin.CODE
            )
        )
    )
    assert facts
    return facts


def _day(session: Session) -> date:
    day = max(_fields(session), key=lambda f: f.significance).event_date
    assert day is not None
    return day


def _read(
    session: Session,
    on: date,
    title: str,
    description: str | None,
    significance: int = 50,
) -> Fact:
    """An incident fact the model read from a note."""
    source = Source(
        matter_id=MATTER_ID,
        clio_type=SourceType.NOTE,
        clio_id=f"account-note-{session.query(Source).count()}",
        raw_json={},
    )
    session.add(source)
    session.flush()
    fact = Fact(
        matter_id=MATTER_ID,
        kind=FactKind.INCIDENT,
        title=title,
        value_json=validate_payload(FactKind.INCIDENT, {"description": description}),
        event_date=on,
        source_id=source.id,
        quote=title,
        significance=significance,
        confidence=Confidence.HIGH,
        origin=Origin.MODEL,
    )
    session.add(fact)
    session.commit()
    return fact


def _account(client: TestClient) -> dict[str, Any] | None:
    response = client.get(f"/api/matters/{MATTER_ID}")
    assert response.status_code == 200, response.text
    return response.json()["incident_account"]


def test_the_fixture_has_a_field_fact_with_no_description(seeded: Session) -> None:
    assert any(not f.value_json.get("description") for f in _fields(seeded))


def test_with_only_field_facts_there_is_no_account(
    seeded: Session, client: TestClient
) -> None:
    assert _account(client) is None


def test_only_the_bare_field_fact_gives_no_account(
    seeded: Session, client: TestClient
) -> None:
    for fact in _fields(seeded):
        if fact.value_json.get("description"):
            seeded.delete(fact)
    seeded.commit()

    assert _account(client) is None


def test_the_account_is_the_described_model_read_never_the_field(
    seeded: Session, client: TestClient
) -> None:
    day = _day(seeded)
    described = _read(seeded, day, "Collision", "Struck from behind at a light", 40)
    _read(seeded, day, "Crash at an intersection", None, 99)

    account = _account(client)

    assert account is not None
    assert account["fact"]["id"] == described.id
    assert account["text"] == "Struck from behind at a light"
    assert account["fact"]["id"] not in {f.id for f in _fields(seeded)}


def test_without_a_description_the_most_significant_title_is_used(
    seeded: Session, client: TestClient
) -> None:
    day = _day(seeded)
    _read(seeded, day, "Collision", "  ", 40)
    leading = _read(seeded, day, "Rear-end collision at a light", None, 80)

    account = _account(client)

    assert account is not None
    assert account["fact"]["id"] == leading.id
    assert account["text"] == "Rear-end collision at a light"


def test_a_read_on_another_day_is_not_the_account(
    seeded: Session, client: TestClient
) -> None:
    day = _day(seeded)
    _read(seeded, day + timedelta(days=5), "Collision", "A later collision", 99)

    assert _account(client) is None


def test_equal_reads_are_broken_by_the_lowest_id(seeded: Session) -> None:
    day = _day(seeded)
    first = _read(seeded, day, "Collision", "Struck from behind", 60)
    second = _read(seeded, day, "Collision", "Struck from behind", 60)
    facts = [*_fields(seeded), second, first]

    chosen = incident_account(facts)

    assert chosen is not None and chosen.id == first.id


def test_no_incident_facts_give_no_account() -> None:
    assert incident_account([]) is None
