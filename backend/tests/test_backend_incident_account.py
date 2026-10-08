"""The header's account of the incident is the one most records read on the incident day
give, never the date-of-incident field, whose title is a label (D39)."""

from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Confidence, Fact, FactKind, Origin, Source, SourceType
from app.schemas import validate_payload
from app.services.incident import incident_account, names_an_event
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


def _reads(session: Session) -> list[Fact]:
    return list(
        session.scalars(
            select(Fact).where(
                Fact.kind == FactKind.INCIDENT, Fact.origin == Origin.MODEL
            )
        )
    )


@pytest.fixture
def bare(seeded: Session) -> Session:
    """The synthetic matter without its model reads of the incident: field facts only,
    so a test's own reads are all there is to choose from."""
    for fact in _reads(seeded):
        seeded.delete(fact)
    seeded.commit()
    return seeded


def _day(session: Session) -> date:
    day = max(_fields(session), key=lambda f: f.significance).event_date
    assert day is not None
    return day


def _note(session: Session) -> Source:
    source = Source(
        matter_id=MATTER_ID,
        clio_type=SourceType.NOTE,
        clio_id=f"account-note-{session.query(Source).count()}",
        raw_json={},
    )
    session.add(source)
    session.flush()
    return source


def _read(
    session: Session,
    on: date,
    title: str,
    significance: int = 50,
    description: str | None = None,
    source: Source | None = None,
) -> Fact:
    """An incident fact the model read from a new note, or from `source`."""
    source = source or _note(session)
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


def _written(day: date) -> str:
    return f"{day:%B} {day.day}, {day.year}"


def test_the_fixture_has_a_field_fact_with_no_description(seeded: Session) -> None:
    assert any(not f.value_json.get("description") for f in _fields(seeded))


def test_with_only_field_facts_there_is_no_account(
    bare: Session, client: TestClient
) -> None:
    assert _account(client) is None


def test_only_the_bare_field_fact_gives_no_account(
    bare: Session, client: TestClient
) -> None:
    for fact in _fields(bare):
        if fact.value_json.get("description"):
            bare.delete(fact)
    bare.commit()

    assert _account(client) is None


def test_the_synthetic_matter_gives_one_account_citing_both_records(
    seeded: Session, client: TestClient
) -> None:
    reads = {f.title: f for f in _reads(seeded)}
    lead = reads["Rear-end collision at a stoplight"]
    again = reads["Client in a rear-end collision at a stoplight"]
    date_only = [f for f in reads.values() if not names_an_event(f.title)]

    account = _account(client)

    assert account is not None
    assert account["fact"]["id"] == lead.id and account["text"] == lead.title
    assert [ref["id"] for ref in account["restated_by"]] == [again.id]
    assert date_only  # the fixture holds one, and the account leaves it out
    cited = {account["fact"]["id"]} | {ref["id"] for ref in account["restated_by"]}
    assert not cited & {f.id for f in date_only}


def test_the_account_most_records_give_beats_a_more_significant_one(
    bare: Session, client: TestClient
) -> None:
    day = _day(bare)
    group = [
        _read(bare, day, "Rear-end collision at a stop light", 50),
        _read(bare, day, "Rear-end collision at a light", 45),
        _read(bare, day, "Rear-end collision at stop light", 40),
    ]
    _read(bare, day, "Pedestrian struck in a crosswalk", 99)

    account = _account(client)

    assert account is not None
    assert account["fact"]["id"] == group[0].id
    assert account["text"] == "Rear-end collision at a stop light"
    assert [ref["id"] for ref in account["restated_by"]] == [g.id for g in group[1:]]
    assert account["fact"]["id"] not in {f.id for f in _fields(bare)}


def test_a_record_restating_the_account_on_many_pages_is_cited_once(
    bare: Session, client: TestClient
) -> None:
    day = _day(bare)
    lead = _read(bare, day, "Rear-end collision at a stoplight", 60)
    record = _note(bare)
    pages = [
        _read(bare, day, "Rear-end collision at a stoplight", 50, source=record)
        for _ in range(3)
    ]

    account = _account(client)

    assert account is not None and account["fact"]["id"] == lead.id
    assert [ref["id"] for ref in account["restated_by"]] == [pages[0].id]


def test_records_are_counted_not_pages(bare: Session, client: TestClient) -> None:
    day = _day(bare)
    record = _note(bare)
    for _ in range(3):
        _read(bare, day, "Pedestrian struck in a crosswalk", 90, source=record)
    told = [_read(bare, day, "Rear-end collision at a stoplight", 40) for _ in range(2)]

    account = _account(client)

    assert account is not None and account["fact"]["id"] == told[0].id


def test_titles_that_only_restate_the_date_never_win(
    bare: Session, client: TestClient
) -> None:
    day = _day(bare)
    for title in (
        f"Accident occurred on {_written(day)}",
        f"Date of loss: {day.isoformat()}",
        f"Incident on {day:%m/%d/%Y} at approximately 4:30 p.m.",
        f"Loss occurred around 1430 hours on {_written(day)}",
        f"Accident on {day:%A}, {_written(day)}",
    ):
        _read(bare, day, title, 99)
    told = _read(bare, day, "Struck from behind at a light", 10)

    account = _account(client)

    assert account is not None and account["fact"]["id"] == told.id


def test_with_only_date_titles_there_is_no_account(
    bare: Session, client: TestClient
) -> None:
    day = _day(bare)
    _read(bare, day, f"Accident occurred on {_written(day)}", 99)
    _read(bare, day, f"Date of incident {day.isoformat()}", 99)

    assert _account(client) is None


@pytest.mark.parametrize(
    ("title", "names"),
    [
        ("Incident on Mar 3rd 2031 approx 2 pm", False),
        ("DOI 03/03/2031 at 14:30", False),
        ("Loss date", False),
        ("Rear-end collision", True),
        ("Struck by a delivery van on March 3, 2031", True),
    ],
)
def test_a_title_names_an_event_only_beyond_its_date(title: str, names: bool) -> None:
    assert names_an_event(title) is names


def test_the_text_is_the_title_even_when_a_description_exists(
    bare: Session, client: TestClient
) -> None:
    day = _day(bare)
    _read(
        bare,
        day,
        "Struck from behind at a light",
        description="Unit two northbound, report 0000",
    )

    account = _account(client)

    assert account is not None and account["text"] == "Struck from behind at a light"


def test_a_read_on_another_day_is_not_the_account(
    bare: Session, client: TestClient
) -> None:
    day = _day(bare)
    _read(bare, day + timedelta(days=5), "Struck from behind at a light", 99)

    assert _account(client) is None


def test_a_tie_in_size_goes_to_significance_then_the_lowest_id(
    seeded: Session,
) -> None:
    day = _day(seeded)
    first = _read(seeded, day, "Struck from behind at a light", 60)
    second = _read(seeded, day, "Sideswiped while merging", 60)
    stronger = _read(seeded, day, "Hit by a turning truck", 70)
    fields = _fields(seeded)

    assert incident_account([*fields, second, first]) == [first]
    assert incident_account([*fields, first, second, stronger]) == [stronger]


def test_no_incident_facts_give_no_account() -> None:
    assert incident_account([]) == []
