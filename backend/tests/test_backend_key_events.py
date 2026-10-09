"""Key events: what has happened on a matter, oldest first, each event once (D39).

Most tests build a matter of their own, so every row is accounted for; the last one
exercises the route over the synthetic matter.
"""

from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Confidence, Fact, FactKind, Origin, Source, SourceType
from app.schemas import FactOut, validate_payload
from app.services.matter_queries import (
    FEED_CANDIDATES_PER_ROW,
    KEY_EVENT_KINDS,
    KEY_EVENTS_PER_KIND,
    matter_key_events,
)
from tests.fixtures.synthetic_matter import MATTER_ID

MATTER = 7  # built by the tests below, so no fixture fact is in the way
TODAY = date(2031, 6, 15)
_REQUIRED: dict[FactKind, dict[str, Any]] = {
    FactKind.STATUS_CHANGE: {"label": "Moved on"},
    FactKind.TASK: {"status": "open"},
}


def _add(
    session: Session,
    kind: FactKind,
    title: str,
    on: date | None,
    significance: int = 50,
    *,
    value: dict[str, Any] | None = None,
    origin: Origin = Origin.MODEL,
    page_cited: bool = True,
    source: Source | None = None,
) -> Fact:
    """A fact from a new note, or from a document without its page when `page_cited` is
    false, or from `source` when one is given."""
    if source is None:
        source = _source(
            session, SourceType.NOTE if page_cited else SourceType.DOCUMENT
        )
    fact = Fact(
        matter_id=MATTER,
        kind=kind,
        title=title,
        value_json=validate_payload(kind, value or _REQUIRED.get(kind, {})),
        event_date=on,
        source_id=source.id,
        quote=title if page_cited else None,
        significance=significance,
        confidence=Confidence.HIGH,
        origin=origin,
    )
    session.add(fact)
    session.commit()
    return fact


def _source(session: Session, clio_type: SourceType = SourceType.NOTE) -> Source:
    source = Source(
        matter_id=MATTER,
        clio_type=clio_type,
        clio_id=f"key-event-{session.query(Source).count()}",
        raw_json={},
    )
    session.add(source)
    session.flush()
    return source


def _days_ago(days: int) -> date:
    return TODAY - timedelta(days=days)


def _incident(session: Session) -> Fact:
    return _add(
        session,
        FactKind.INCIDENT,
        "Date of loss",
        _days_ago(300),
        40,
        origin=Origin.CODE,
    )


def _events(session: Session, limit: int = 10) -> list[FactOut]:
    return matter_key_events(session, MATTER, TODAY, limit)


def _ids(rows: list[FactOut]) -> set[int]:
    return {row.id for row in rows}


def _incident_rows(rows: list[FactOut]) -> list[int]:
    return [row.id for row in rows if row.kind is FactKind.INCIDENT]


def test_the_incident_is_one_row_however_many_incident_facts(
    session: Session,
) -> None:
    field = _incident(session)
    assert field.event_date is not None
    told = [
        _add(session, FactKind.INCIDENT, f"Collision account {n}", field.event_date, 99)
        for n in range(4)
    ]
    _add(session, FactKind.INCIDENT, "Collision", _days_ago(290), 99)
    _add(session, FactKind.DIAGNOSIS, "Sprain diagnosed", _days_ago(280), 60)

    rows = _events(session)

    assert _incident_rows(rows) == [told[0].id]  # the account: lowest id of equals
    assert len(rows) == 2


def test_the_incident_row_is_the_model_read_account_over_the_field(
    session: Session,
) -> None:
    field = _incident(session)
    told = _add(
        session,
        FactKind.INCIDENT,
        "Struck from behind at a light",
        field.event_date,
        30,
        value={"description": "Struck from behind at a light"},
    )

    assert _incident_rows(_events(session)) == [told.id]


def test_the_incident_row_cites_every_record_that_gives_the_account(
    session: Session,
) -> None:
    field = _incident(session)
    group = [
        _add(
            session,
            FactKind.INCIDENT,
            "Rear-end collision at a light",
            field.event_date,
        )
        for _ in range(3)
    ]
    _add(session, FactKind.INCIDENT, "Pedestrian struck", field.event_date, 99)
    _add(session, FactKind.INCIDENT, "Accident on date of loss", field.event_date, 99)

    row = next(r for r in _events(session) if r.kind is FactKind.INCIDENT)

    assert row.id == group[0].id
    assert [ref.id for ref in row.restated_by] == [f.id for f in group[1:]]


def test_with_only_the_field_the_incident_row_is_the_field(
    session: Session,
) -> None:
    field = _incident(session)

    assert _incident_rows(_events(session)) == [field.id]


def test_twelve_significant_diagnoses_give_three_rows(session: Session) -> None:
    _incident(session)
    for n in range(12):
        _add(session, FactKind.DIAGNOSIS, f"Finding {n}", _days_ago(200 - n), 95)

    rows = _events(session)

    diagnoses = [row for row in rows if row.kind is FactKind.DIAGNOSIS]
    assert len(diagnoses) == KEY_EVENTS_PER_KIND == 3


def test_a_numerous_kind_does_not_crowd_out_the_others(session: Session) -> None:
    _incident(session)
    limit = 5
    # More diagnoses than one candidate window over every kind would read.
    for n in range(limit * FEED_CANDIDATES_PER_ROW + 1):
        _add(session, FactKind.DIAGNOSIS, f"Finding {n}", _days_ago(200 - n), 95)
    visit = _add(session, FactKind.TREATMENT_VISIT, "Visit", _days_ago(100), 5)

    rows = _events(session, limit)

    assert visit.id in _ids(rows)
    assert len(rows) == limit


def test_only_past_dated_events_are_listed(session: Session) -> None:
    incident = _incident(session)
    past = _add(session, FactKind.DIAGNOSIS, "Past finding", _days_ago(10), 1)
    left_out = [
        _add(session, FactKind.DIAGNOSIS, "Future finding", TODAY + timedelta(1), 100),
        _add(session, FactKind.DIAGNOSIS, "Undated finding", None, 100),
        _add(session, FactKind.TASK, "Call the adjuster", _days_ago(5), 100),
        _add(session, FactKind.LIABILITY, "Liability looks clear", _days_ago(5), 100),
        _add(session, FactKind.CALL_NOTE, "Promised the records", _days_ago(5), 100),
        _add(session, FactKind.POLICY_LIMIT, "Limit stated", _days_ago(5), 100),
        _add(session, FactKind.CASE_STAGE, "Treatment", _days_ago(5), 100),
        _add(session, FactKind.MEDICAL_BILL, "Bill", _days_ago(5), 100),
    ]

    rows = _events(session)

    assert _ids(rows) == {incident.id, past.id}
    assert not _ids(rows) & {f.id for f in left_out}
    assert {row.kind for row in rows} <= {*KEY_EVENT_KINDS, FactKind.INCIDENT}


def test_a_litigation_event_that_happened_is_a_key_event(session: Session) -> None:
    _incident(session)
    filed = _add(
        session,
        FactKind.LITIGATION_EVENT,
        "Complaint filed",
        _days_ago(90),
        value={"event": "filed"},
    )
    set_for_later = _add(
        session,
        FactKind.LITIGATION_EVENT,
        "Trial",
        TODAY + timedelta(days=30),
        100,
        value={"event": "trial"},
    )
    undated = _add(
        session,
        FactKind.LITIGATION_EVENT,
        "Answer",
        None,
        100,
        value={"event": "answered"},
    )

    ids = _ids(_events(session))

    assert FactKind.LITIGATION_EVENT in KEY_EVENT_KINDS
    assert filed.id in ids
    assert not {set_for_later.id, undated.id} & ids


def _court_event(
    session: Session, title: str, on: date | None, significance: int
) -> Fact:
    return _add(
        session,
        FactKind.LITIGATION_EVENT,
        title,
        on,
        significance,
        value={"event": "other"},
    )


def test_court_events_are_pinned_however_low_their_score(session: Session) -> None:
    incident = _incident(session)
    for n in range(10):
        _add(session, FactKind.DIAGNOSIS, f"Finding {n}", _days_ago(200 - n), 95)
        _add(session, FactKind.TREATMENT_VISIT, f"Visit {n}", _days_ago(150 - n), 95)
    court = [
        _court_event(session, "Complaint filed", _days_ago(120), 10),
        _court_event(session, "Answer received", _days_ago(90), 5),
    ]

    rows = _events(session, limit=5)

    assert len(rows) == 5
    ids = _ids(rows)
    assert incident.id in ids
    assert {f.id for f in court} <= ids
    assert [(r.event_date, r.id) for r in rows] == sorted(
        (r.event_date, r.id) for r in rows
    )


def test_court_events_beyond_the_cap_or_undated_are_left_out(
    session: Session,
) -> None:
    _incident(session)
    kept = [
        _court_event(session, "Complaint filed", _days_ago(120), 40),
        _court_event(session, "Defendant served", _days_ago(110), 30),
        _court_event(session, "Answer received", _days_ago(90), 20),
    ]
    beyond = _court_event(session, "Motion argued", _days_ago(60), 10)
    undated = _court_event(session, "Case renewed", None, 100)

    ids = _ids(_events(session))

    assert {f.id for f in kept} <= ids
    assert beyond.id not in ids
    assert undated.id not in ids


def test_a_limit_below_what_is_pinned_keeps_the_incident_first(
    session: Session,
) -> None:
    incident = _incident(session)
    _court_event(session, "Complaint filed", _days_ago(120), 10)
    stronger = _court_event(session, "Defendant served", _days_ago(110), 60)

    assert _ids(_events(session, limit=2)) == {incident.id, stronger.id}
    assert _ids(_events(session, limit=1)) == {incident.id}


def test_a_deadline_is_never_a_key_event(session: Session) -> None:
    """A date set for a hearing does not say the hearing took place (D40)."""
    _incident(session)
    due = datetime.combine(_days_ago(1), time(17, 0), UTC).isoformat()
    scheduled = _add(
        session,
        FactKind.DEADLINE,
        "Hearing",
        _days_ago(1),
        100,
        value={"deadline_type": "hearing", "due_at": due},
    )

    assert FactKind.DEADLINE not in KEY_EVENT_KINDS
    assert scheduled.id not in _ids(_events(session))


def test_a_restated_event_is_one_row_citing_the_other_record(
    session: Session,
) -> None:
    _incident(session)
    day = _days_ago(50)
    lead = _add(session, FactKind.DIAGNOSIS, "Wrist sprain diagnosed", day, 100)
    again = _add(session, FactKind.DIAGNOSIS, "Wrist sprain diagnosed on exam", day, 99)

    rows = _events(session)

    assert lead.id in _ids(rows) and again.id not in _ids(rows)
    row = next(r for r in rows if r.id == lead.id)
    assert [ref.id for ref in row.restated_by] == [again.id]


def test_a_record_restating_an_event_on_many_pages_is_cited_once(
    session: Session,
) -> None:
    _incident(session)
    day = _days_ago(50)
    lead_record, other_record = _source(session), _source(session)

    def finding(source: Source, significance: int) -> Fact:
        return _add(
            session,
            FactKind.DIAGNOSIS,
            "Wrist sprain diagnosed",
            day,
            significance,
            source=source,
        )

    lead = finding(lead_record, 100)
    finding(lead_record, 99)  # another page of the lead's own record
    pages = [finding(other_record, 98 - n) for n in range(3)]

    row = next(r for r in _events(session) if r.id == lead.id)

    assert [ref.id for ref in row.restated_by] == [pages[0].id]


def test_the_incident_row_cites_each_record_once(session: Session) -> None:
    field = _incident(session)
    record = _source(session)
    lead = _add(session, FactKind.INCIDENT, "Rear-end collision", field.event_date, 60)
    pages = [
        _add(
            session,
            FactKind.INCIDENT,
            "Rear-end collision",
            field.event_date,
            50,
            source=record,
        )
        for _ in range(3)
    ]

    row = next(r for r in _events(session) if r.kind is FactKind.INCIDENT)

    assert row.id == lead.id
    assert [ref.id for ref in row.restated_by] == [pages[0].id]


def test_oldest_first_within_the_limit(session: Session) -> None:
    incident = _incident(session)
    kinds = (
        FactKind.DIAGNOSIS,
        FactKind.TREATMENT_VISIT,
        FactKind.RECORDS_RECEIVED,
        FactKind.DEMAND,
    )
    for n, kind in enumerate(kinds * 2):
        _add(session, kind, f"Event {n}", _days_ago(20 * (n + 1)), 50 + n)

    rows = _events(session, limit=4)

    assert len(rows) == 4
    assert rows[0].id == incident.id  # the oldest, and counted toward the limit
    assert [(r.event_date, r.id) for r in rows] == sorted(
        (r.event_date, r.id) for r in rows
    )
    # The most significant three of the rest, not the oldest three.
    assert {r.title for r in rows[1:]} == {"Event 7", "Event 6", "Event 5"}
    assert [r.id for r in _events(session, limit=1)] == [incident.id]


def test_a_document_fact_without_its_page_is_never_listed(session: Session) -> None:
    _incident(session)
    unsourced = _add(
        session, FactKind.DIAGNOSIS, "Finding", _days_ago(5), 100, page_cited=False
    )

    assert unsourced.id not in _ids(_events(session))


def test_a_matter_with_no_facts_has_no_key_events(session: Session) -> None:
    assert _events(session) == []


def test_the_route_lists_the_synthetic_matter_and_refuses_unknown_ones(
    seeded: Session, client: TestClient
) -> None:
    response = client.get(f"/api/matters/{MATTER_ID}/key-events")
    assert response.status_code == 200, response.text
    rows = response.json()
    header = client.get(f"/api/matters/{MATTER_ID}").json()

    assert rows and len(rows) <= 10
    today = datetime.now(UTC).date().isoformat()
    assert all(row["event_date"] and row["event_date"] <= today for row in rows)
    incidents = [row for row in rows if row["kind"] == "incident"]
    # The synthetic matter's account is restated by a second record (the fixture).
    account = header["incident_account"]
    assert account and account["restated_by"]
    assert [row["id"] for row in incidents] == [account["fact"]["id"]]
    assert incidents[0]["restated_by"] == account["restated_by"]
    assert [r["event_date"] for r in rows] == sorted(r["event_date"] for r in rows)

    assert client.get("/api/matters/999/key-events").status_code == 404
    assert client.get(f"/api/matters/{MATTER_ID}/key-events?limit=0").status_code == 422
    assert len(client.get(f"/api/matters/{MATTER_ID}/key-events?limit=2").json()) == 2
