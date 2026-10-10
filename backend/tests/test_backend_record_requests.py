"""Record requests close when the file shows them answered (critic finding 8).

A request fact keeps the status it had when it was written. These tests add requests
and receipts to the synthetic matter and read the three places that list requests: the
providers panel, the provider's link, and the action board.
"""

from datetime import date, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Confidence,
    Fact,
    FactKind,
    Origin,
    Source,
    SourceType,
    User,
    Visibility,
)
from tests.fixtures.synthetic_matter import MATTER_ID, ORTHO_ID, THERAPY_ID


@pytest.fixture
def user_id(seeded: Session) -> int:
    user = User(name="Test paralegal", role="paralegal")
    seeded.add(user)
    seeded.commit()
    return user.id


def _add(
    session: Session,
    kind: FactKind,
    on: date | None,
    provider: int | None = THERAPY_ID,
    value: dict[str, Any] | None = None,
) -> Fact:
    source = Source(
        matter_id=MATTER_ID,
        clio_type=SourceType.COMMUNICATION,
        clio_id=f"request-email-{session.query(Source).count()}",
        raw_json={},
    )
    session.add(source)
    session.flush()
    fact = Fact(
        matter_id=MATTER_ID,
        kind=kind,
        title=f"{kind.value} {on}",
        value_json=value
        if value is not None
        else ({"status": "open"} if kind is FactKind.RECORD_REQUEST else {}),
        event_date=on,
        source_id=source.id,
        quote="Quoted from the email",
        provider_contact_id=provider,
        visibility=Visibility.SHAREABLE,
        confidence=Confidence.HIGH,
        origin=Origin.MODEL,
    )
    session.add(fact)
    session.commit()
    return fact


def _earliest(session: Session) -> date:
    """A day before every date in the synthetic matter."""
    days = session.scalars(select(Fact.event_date).where(Fact.event_date.is_not(None)))
    return min(days) - timedelta(days=400)


def _open_count(client: TestClient, provider: int = THERAPY_ID) -> int:
    rows = client.get(f"/api/matters/{MATTER_ID}/providers").json()
    return next(r["open_requests"] for r in rows if r["contact_id"] == provider)


def _link_requests(client: TestClient, user_id: int) -> list[int]:
    response = client.post(
        f"/api/matters/{MATTER_ID}/shares",
        json={"provider_contact_id": THERAPY_ID},
        headers={"X-User-Id": str(user_id)},
    )
    share = response.json()
    preview = client.get(f"/api/shares/{share['id']}/preview").json()["payload"]
    return [item["fact_id"] for item in preview["requests"]]


def _waiting(client: TestClient) -> set[int]:
    board = client.get(f"/api/matters/{MATTER_ID}/actions").json()
    return {row["id"] for row in board["waiting_on_others"]}


def test_a_request_answered_by_later_records_is_closed_everywhere(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    day = _earliest(seeded)
    asked = _add(seeded, FactKind.RECORD_REQUEST, day)
    _add(seeded, FactKind.RECORDS_RECEIVED, day + timedelta(days=30))

    assert _open_count(client) == 0
    assert _link_requests(client, user_id) == []
    assert asked.id not in _waiting(client)


def test_records_from_another_provider_or_from_before_answer_nothing(
    seeded: Session, client: TestClient
) -> None:
    day = _earliest(seeded)
    asked = _add(seeded, FactKind.RECORD_REQUEST, day)
    _add(seeded, FactKind.RECORDS_RECEIVED, day + timedelta(days=30), ORTHO_ID)
    _add(seeded, FactKind.RECORDS_RECEIVED, day - timedelta(days=30))

    assert _open_count(client) == 1
    assert asked.id in _waiting(client)


def test_every_ask_since_the_last_records_is_one_request_the_latest(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    day = _earliest(seeded)
    _add(seeded, FactKind.RECORDS_RECEIVED, day)
    asks = [
        _add(seeded, FactKind.RECORD_REQUEST, day + timedelta(days=d))
        for d in (10, 40, 70)
    ]
    _add(seeded, FactKind.RECORD_REQUEST, None)  # an undated restatement

    assert _open_count(client) == 1
    assert _link_requests(client, user_id) == [asks[-1].id]
    assert _waiting(client) & {a.id for a in asks} == {asks[-1].id}


def test_an_undated_request_stays_open_until_the_provider_sends_dated_records(
    seeded: Session, client: TestClient
) -> None:
    undated = _add(seeded, FactKind.RECORD_REQUEST, None)
    assert _open_count(client) == 1
    assert undated.id in _waiting(client)

    _add(seeded, FactKind.RECORDS_RECEIVED, _earliest(seeded))

    assert _open_count(client) == 0
    assert undated.id not in _waiting(client)


def test_a_request_to_no_provider_keeps_its_own_status(
    seeded: Session, client: TestClient
) -> None:
    day = _earliest(seeded)
    asked = _add(seeded, FactKind.RECORD_REQUEST, day, provider=None)
    again = _add(seeded, FactKind.RECORD_REQUEST, day + timedelta(days=5), None)
    _add(seeded, FactKind.RECORDS_RECEIVED, day + timedelta(days=30), None)

    assert {asked.id, again.id} <= _waiting(client)
