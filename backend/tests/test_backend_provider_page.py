"""The provider's page: when the case last moved, and each policy limit once (findings 12, 16)."""

from datetime import UTC, date, datetime
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
from app.schemas import validate_payload
from tests.fixtures.synthetic_matter import MATTER_ID, ORTHO_ID


@pytest.fixture
def user_id(seeded: Session) -> int:
    user = User(name="Test paralegal", role="paralegal")
    seeded.add(user)
    seeded.commit()
    return user.id


def _payload(client: TestClient, user_id: int, **settings: bool) -> dict[str, Any]:
    response = client.post(
        f"/api/matters/{MATTER_ID}/shares",
        json={"provider_contact_id": ORTHO_ID, "settings": settings},
        headers={"X-User-Id": str(user_id)},
    )
    share = response.json()
    return client.get(f"/api/shares/{share['id']}/preview").json()["payload"]


def _one(session: Session, kind: FactKind) -> Fact:
    return session.scalars(select(Fact).where(Fact.kind == kind)).one()


def test_last_movement_ignores_the_day_clio_last_edited_the_matter(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    stage = _one(seeded, FactKind.CASE_STAGE)
    change = _one(seeded, FactKind.STATUS_CHANGE)
    assert change.event_date is not None
    # The mapped stage carries the matter record's last edit, as the pipeline dates it.
    stage.event_date = datetime.now(UTC).date()
    seeded.commit()

    status = _payload(client, user_id)["status"]

    assert status["last_movement_on"] == change.event_date.isoformat()


def test_no_dated_case_event_means_no_last_movement(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    seeded.delete(_one(seeded, FactKind.STATUS_CHANGE))
    seeded.commit()

    assert _payload(client, user_id)["status"]["last_movement_on"] is None


def _limit(session: Session, value: dict[str, Any], on: date | None) -> Fact:
    source = Source(
        matter_id=MATTER_ID,
        clio_type=SourceType.COMMUNICATION,
        clio_id=f"limit-email-{session.query(Source).count()}",
        raw_json={},
    )
    session.add(source)
    session.flush()
    fact = Fact(
        matter_id=MATTER_ID,
        kind=FactKind.POLICY_LIMIT,
        title="Limit restated",
        value_json=validate_payload(FactKind.POLICY_LIMIT, value),
        event_date=on,
        source_id=source.id,
        quote="Limit restated",
        visibility=Visibility.SHAREABLE,
        confidence=Confidence.HIGH,
        origin=Origin.MODEL,
    )
    session.add(fact)
    session.commit()
    return fact


def _limits_only(session: Session) -> None:
    for fact in session.scalars(select(Fact).where(Fact.kind == FactKind.POLICY_LIMIT)):
        session.delete(fact)
    session.commit()


def _defendants(cents: int, per: str | None) -> dict[str, Any]:
    return {"amount_cents": cents, "per": per, "policy": "defendant_liability"}


def _listed(client: TestClient, user_id: int) -> list[tuple[int, str]]:
    limits = _payload(client, user_id, coverage_limits=True)["coverage"]["limits"]
    return [(item["amount_cents"], item["label"]) for item in limits]


def test_a_limit_stated_by_several_records_is_listed_once(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    _limits_only(seeded)
    _limit(seeded, _defendants(1_000_00, "person"), date(2031, 7, 1))
    _limit(seeded, _defendants(1_000_00, "person"), None)
    _limit(seeded, _defendants(1_000_00, "occurrence"), None)

    assert _listed(client, user_id) == [
        (1_000_00, "Liability limit per person"),
        (1_000_00, "Liability limit per occurrence"),
    ]


def test_a_restated_limit_cites_its_earliest_statement(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    _limits_only(seeded)
    _limit(seeded, _defendants(1_000_00, "person"), date(2031, 7, 1))
    earlier = _limit(seeded, _defendants(1_000_00, "person"), date(2031, 6, 1))

    limits = _payload(client, user_id, coverage_limits=True)["coverage"]["limits"]

    assert [item["fact_id"] for item in limits] == [earlier.id]


# --- D37: the provider sees the defendant's liability limits, labelled by basis -------


def test_the_provider_sees_the_defendants_limits_per_person_first(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    _limits_only(seeded)
    _limit(seeded, _defendants(3_000_00, "occurrence"), date(2031, 6, 1))
    _limit(seeded, _defendants(1_000_00, "person"), date(2031, 7, 1))
    # Beside limits that state a basis, one without is a restatement or a stray.
    _limit(seeded, _defendants(1_000_00, None), None)
    _limit(seeded, _defendants(2_000_00, None), None)
    for policy in ("client_no_fault", "client_um_uim", "client_other", None):
        _limit(
            seeded, {"amount_cents": 500_00, "per": "person", "policy": policy}, None
        )

    assert _listed(client, user_id) == [
        (1_000_00, "Liability limit per person"),
        (3_000_00, "Liability limit per occurrence"),
    ]


def test_a_defendant_limit_with_no_basis_is_listed_when_none_states_one(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    _limits_only(seeded)
    _limit(seeded, _defendants(1_000_00, None), date(2031, 7, 1))
    _limit(seeded, _defendants(1_000_00, None), None)

    assert _listed(client, user_id) == [(1_000_00, "Liability limit")]


# --- K4: last movement never dates the case from an older event ----------------------


def _change(session: Session, to_stage: str | None, on: date | None) -> Fact:
    source = Source(
        matter_id=MATTER_ID,
        clio_type=SourceType.NOTE,
        clio_id=f"stage-note-{session.query(Source).count()}",
        raw_json={},
    )
    session.add(source)
    session.flush()
    fact = Fact(
        matter_id=MATTER_ID,
        kind=FactKind.STATUS_CHANGE,
        title="Stage changed",
        value_json=validate_payload(
            FactKind.STATUS_CHANGE, {"to_stage": to_stage, "label": "The case moved"}
        ),
        event_date=on,
        source_id=source.id,
        quote="The case moved",
        visibility=Visibility.SHAREABLE,
        confidence=Confidence.HIGH,
        origin=Origin.MODEL,
    )
    session.add(fact)
    session.commit()
    return fact


def test_an_undated_later_change_leaves_last_movement_unknown(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    # The case moved on to a stage the dated change does not reach; when is unknown.
    stage = _one(seeded, FactKind.CASE_STAGE)
    stage.value_json = {**stage.value_json, "stage": "litigation"}
    seeded.commit()
    _change(seeded, "litigation", None)

    assert _payload(client, user_id)["status"]["last_movement_on"] is None


def test_a_dated_move_into_the_current_stage_dates_last_movement(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    stage = _one(seeded, FactKind.CASE_STAGE)
    stage.value_json = {**stage.value_json, "stage": "litigation"}
    seeded.commit()
    moved = _change(seeded, "litigation", date(2031, 7, 14))
    _change(seeded, None, None)  # an undated note of some earlier step

    status = _payload(client, user_id)["status"]

    assert status["last_movement_on"] == moved.event_date.isoformat()
