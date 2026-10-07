"""D35: a provider item says whether it is a bill or a lien, on the link and the previews."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Fact, FactKind, User
from app.services.visibility import KINDS_BY_SETTING
from tests.fixtures.synthetic_matter import MATTER_ID, ORTHO_ID, THERAPY_ID

EVERY_SETTING = dict.fromkeys(KINDS_BY_SETTING, True)
VIEWS = ["link", "preview", "draft"]


@pytest.fixture
def user_id(seeded: Session) -> int:
    user = User(name="Test paralegal", role="paralegal")
    seeded.add(user)
    seeded.commit()
    return user.id


def _ok(response: Any) -> Any:
    assert response.status_code in (200, 201), response.text
    return response.json()


def _payload(
    client: TestClient, user_id: int, provider: int, view: str
) -> dict[str, Any]:
    """The payload as the provider's link, the saved share's preview, or a draft shows it."""
    body = {"provider_contact_id": provider, "settings": EVERY_SETTING}
    if view == "draft":
        draft = client.post(f"/api/matters/{MATTER_ID}/shares/preview", json=body)
        return _ok(draft)["payload"]
    share = _ok(
        client.post(
            f"/api/matters/{MATTER_ID}/shares",
            json=body,
            headers={"X-User-Id": str(user_id)},
        )
    )
    if view == "preview":
        return _ok(client.get(f"/api/shares/{share['id']}/preview"))["payload"]
    return _ok(client.get(f"/api/p/{share['url'].rsplit('/p/', 1)[1]}"))


def _items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    limits = (payload["coverage"] or {}).get("limits") or []
    sections = ("requests", "bills", "records")
    return [item for s in sections for item in payload[s] or []] + limits


def _own(session: Session, kind: FactKind, provider: int) -> Fact:
    fact = session.scalars(
        select(Fact).where(Fact.kind == kind, Fact.provider_contact_id == provider)
    ).first()
    assert fact is not None, f"the seed has no {kind} for provider {provider}"
    return fact


@pytest.mark.parametrize("view", VIEWS)
def test_a_lien_says_lien_and_a_bill_says_bill(
    seeded: Session, client: TestClient, user_id: int, view: str
) -> None:
    bill = _own(seeded, FactKind.MEDICAL_BILL, ORTHO_ID)
    lien = _own(seeded, FactKind.LIEN, ORTHO_ID)

    payload = _payload(client, user_id, ORTHO_ID, view)

    assert {b["fact_id"]: b["kind"] for b in payload["bills"]} == {
        bill.id: "bill",
        lien.id: "lien",
    }


@pytest.mark.parametrize("view", VIEWS)
def test_records_requests_and_limits_carry_no_kind(
    seeded: Session, client: TestClient, user_id: int, view: str
) -> None:
    payload = _payload(client, user_id, ORTHO_ID, view)

    others = [payload["records"], payload["requests"], payload["coverage"]["limits"]]
    # Each section has items, so their empty kinds mean something.
    assert all(others)
    assert all(item["kind"] is None for section in others for item in section)


def test_the_bills_total_still_counts_bills_only(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    payload = _payload(client, user_id, ORTHO_ID, "link")

    bills = [b for b in payload["bills"] if b["kind"] == "bill"]
    assert any(b["kind"] == "lien" for b in payload["bills"])
    assert payload["bills_total"] == {
        "amount_cents": sum(b["amount_cents"] for b in bills),
        "bill_count": len(bills),
    }


def test_a_provider_with_bills_and_no_lien_gets_no_lien(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    payload = _payload(client, user_id, THERAPY_ID, "link")

    assert [b["kind"] for b in payload["bills"]] == ["bill"]
    assert all(item["kind"] != "lien" for item in _items(payload))


@pytest.mark.parametrize("view", VIEWS)
def test_a_provider_with_neither_gets_no_such_items(
    seeded: Session, client: TestClient, user_id: int, view: str
) -> None:
    seeded.delete(_own(seeded, FactKind.MEDICAL_BILL, THERAPY_ID))
    seeded.commit()

    payload = _payload(client, user_id, THERAPY_ID, view)

    assert payload["bills"] == []
    assert payload["bills_total"] is None
    assert all(item["kind"] is None for item in _items(payload))
