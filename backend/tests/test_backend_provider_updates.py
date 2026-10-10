"""A provider's case updates are moves to a stage, in words written in code; a status
change's own wording never reaches a provider or the firm's preview of the link (D41)."""

import json
from datetime import UTC, date, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import (
    Confidence,
    Fact,
    FactKind,
    Origin,
    Source,
    SourceType,
    Visibility,
)
from app.schemas import validate_payload
from tests.fixtures.synthetic_matter import MATTER_ID, ORTHO_ID

# Invented wording that a record might use and a provider must not read.
FREE_TEXT = "Paused while the firm weighs a sensitive internal question"


def _status_change(
    session: Session, to_stage: str | None, label: str, on: date
) -> Fact:
    source = Source(
        matter_id=MATTER_ID,
        clio_type=SourceType.NOTE,
        clio_id=f"status-note-{session.query(Source).count()}",
        raw_json={},
    )
    session.add(source)
    session.flush()
    fact = Fact(
        matter_id=MATTER_ID,
        kind=FactKind.STATUS_CHANGE,
        title=label,
        value_json=validate_payload(
            FactKind.STATUS_CHANGE, {"to_stage": to_stage, "label": label}
        ),
        event_date=on,
        source_id=source.id,
        quote=label,
        # Tagged shareable, as the kind is: the stage alone must decide.
        visibility=Visibility.SHAREABLE,
        significance=80,
        confidence=Confidence.HIGH,
        origin=Origin.MODEL,
    )
    session.add(fact)
    session.commit()
    return fact


def _preview(client: TestClient) -> dict[str, Any]:
    response = client.post(
        f"/api/matters/{MATTER_ID}/shares/preview",
        json={"provider_contact_id": ORTHO_ID},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_a_status_without_a_stage_never_reaches_the_link_or_the_preview(
    seeded: Session, client: TestClient
) -> None:
    free = _status_change(
        seeded, None, FREE_TEXT, datetime.now(UTC).date() - timedelta(days=3)
    )

    preview = _preview(client)

    assert FREE_TEXT not in json.dumps(preview["payload"])
    assert free.id not in {item["fact_id"] for item in preview["items"]}
    assert all(u["label"] != FREE_TEXT for u in preview["payload"]["updates"])


def test_a_move_to_a_stage_is_labelled_in_code_not_in_the_records_words(
    seeded: Session, client: TestClient
) -> None:
    move = _status_change(
        seeded, "litigation", FREE_TEXT, datetime.now(UTC).date() - timedelta(days=2)
    )

    preview = _preview(client)

    updates = preview["payload"]["updates"]
    assert updates[0] == {
        "on": move.event_date.isoformat(),
        "label": "Moved to litigation",
    }
    assert FREE_TEXT not in json.dumps(preview["payload"])
    assert move.id in {item["fact_id"] for item in preview["items"]}
