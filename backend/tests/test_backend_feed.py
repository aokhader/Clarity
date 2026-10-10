"""The ranked feed lists each fact once, citing every record that restates it (finding 9)."""

from datetime import date
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Confidence, Fact, FactKind, Origin, Source, SourceType
from app.schemas import validate_payload
from tests.fixtures.synthetic_matter import MATTER_ID


def _add(
    session: Session,
    kind: FactKind,
    title: str,
    value: dict[str, Any],
    on: date | None = None,
    significance: int = 100,
    source: Source | None = None,
) -> Fact:
    if source is None:
        source = Source(
            matter_id=MATTER_ID,
            clio_type=SourceType.NOTE,
            clio_id=f"feed-note-{session.query(Source).count()}",
            raw_json={},
        )
        session.add(source)
        session.flush()
    fact = Fact(
        matter_id=MATTER_ID,
        kind=kind,
        title=title,
        value_json=validate_payload(kind, value),
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


def _feed(client: TestClient, limit: int = 10) -> list[dict[str, Any]]:
    response = client.get(f"/api/matters/{MATTER_ID}/feed?limit={limit}")
    assert response.status_code == 200, response.text
    return response.json()


def _restated(row: dict[str, Any]) -> set[int]:
    return {ref["id"] for ref in row["restated_by"]}


def test_a_figure_stated_by_three_records_is_one_row_citing_all(
    seeded: Session, client: TestClient
) -> None:
    limit = {"amount_cents": 7_700_000, "per": "person"}
    lead = _add(seeded, FactKind.POLICY_LIMIT, "Limit of $77,000", limit)
    again = [
        _add(
            seeded, FactKind.POLICY_LIMIT, "Per-person cap", limit, date(2031, 7, 1), 99
        ),
        _add(seeded, FactKind.POLICY_LIMIT, "Their limit", limit, None, 98),
    ]

    feed = _feed(client)
    ids = [row["id"] for row in feed]

    assert lead.id in ids and not {a.id for a in again} & set(ids)
    row = next(r for r in feed if r["id"] == lead.id)
    assert _restated(row) == {a.id for a in again}
    assert len(feed) == 10  # the freed slots go to the next facts


def test_a_record_stating_a_figure_on_many_pages_is_cited_once(
    seeded: Session, client: TestClient
) -> None:
    limit = {"amount_cents": 7_700_000, "per": "person"}
    lead = _add(seeded, FactKind.POLICY_LIMIT, "Limit of $77,000", limit)
    record = seeded.get(Source, lead.source_id)
    assert record is not None
    other = Source(
        matter_id=MATTER_ID,
        clio_type=SourceType.NOTE,
        clio_id="feed-pages",
        raw_json={},
    )
    seeded.add(other)
    seeded.flush()
    _add(seeded, FactKind.POLICY_LIMIT, "Limit", limit, None, 99, source=record)
    pages = [
        _add(seeded, FactKind.POLICY_LIMIT, "Limit", limit, None, 98 - n, source=other)
        for n in range(3)
    ]

    row = next(r for r in _feed(client) if r["id"] == lead.id)

    assert _restated(row) == {pages[0].id}


def test_the_same_finding_in_other_words_is_one_row(
    seeded: Session, client: TestClient
) -> None:
    detail = {"detail": "Inconsistent accounts"}
    lead = _add(
        seeded, FactKind.OTHER, "Client gave three inconsistent accounts", detail
    )
    again = _add(
        seeded,
        FactKind.OTHER,
        "Client gave three inconsistent accounts of the collision",
        detail,
        significance=99,
    )

    row = next(r for r in _feed(client) if r["id"] == lead.id)

    assert _restated(row) == {again.id}


def test_like_events_on_different_days_stay_apart(
    seeded: Session, client: TestClient
) -> None:
    visit = {"visit_type": "physical therapy"}
    first = _add(
        seeded, FactKind.TREATMENT_VISIT, "Therapy session", visit, date(2031, 7, 1)
    )
    second = _add(
        seeded, FactKind.TREATMENT_VISIT, "Therapy session", visit, date(2031, 7, 8)
    )

    ids = [row["id"] for row in _feed(client)]

    assert first.id in ids and second.id in ids


def test_different_figures_of_one_kind_stay_apart(
    seeded: Session, client: TestClient
) -> None:
    person = _add(
        seeded,
        FactKind.POLICY_LIMIT,
        "Limit",
        {"amount_cents": 7_700_000, "per": "person"},
    )
    occurrence = _add(
        seeded,
        FactKind.POLICY_LIMIT,
        "Limit",
        {"amount_cents": 7_700_000, "per": "occurrence"},
    )

    ids = [row["id"] for row in _feed(client)]

    assert person.id in ids and occurrence.id in ids
