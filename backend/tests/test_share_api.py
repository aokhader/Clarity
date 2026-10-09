"""Share management and the provider link, exercised over HTTP against the synthetic matter."""

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Fact, FactKind, Share, User, Visibility
from app.services.visibility import SETTING_BY_KIND
from tests.fixtures.synthetic_matter import (
    CLIENT_ID,
    INSURER_ID,
    MATTER_ID,
    ORTHO_ID,
    THERAPY_ID,
)


@pytest.fixture
def user_id(seeded: Session) -> int:
    user = User(name="Test paralegal", role="paralegal")
    seeded.add(user)
    seeded.commit()
    return user.id


def _ok(response: Any, status: int = 200) -> Any:
    assert response.status_code == status, response.text
    return response.json()


def _create(
    client: TestClient, user_id: int, provider: int = ORTHO_ID, **body: Any
) -> dict[str, Any]:
    response = client.post(
        f"/api/matters/{MATTER_ID}/shares",
        json={"provider_contact_id": provider} | body,
        headers={"X-User-Id": str(user_id)},
    )
    return _ok(response, 201)


def _token(share: dict[str, Any]) -> str:
    return share["url"].rsplit("/p/", 1)[1]


def _fact(session: Session, kind: FactKind, provider: int | None) -> Fact:
    fact = session.scalars(
        select(Fact).where(Fact.kind == kind, Fact.provider_contact_id == provider)
    ).first()
    assert fact is not None
    return fact


def test_create_then_open_records_the_visit(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    share = _create(client, user_id)
    assert share["opened_count"] == 0
    assert share["revoked_at"] is None
    expires = datetime.fromisoformat(share["expires_at"])
    assert timedelta(days=29) < expires - datetime.now(UTC) <= timedelta(days=30)

    response = client.get(f"/api/p/{_token(share)}")
    _ok(response)
    assert response.headers["cache-control"] == "no-store"

    [listed] = _ok(client.get(f"/api/matters/{MATTER_ID}/shares"))
    assert listed["id"] == share["id"]
    assert listed["opened_count"] == 1
    assert listed["last_opened_at"] is not None


def test_default_payload_has_status_coverage_and_own_items_only(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    payload = _ok(client.get(f"/api/p/{_token(_create(client, user_id))}"))

    assert payload["status"]["current"] == "treating"
    assert payload["status"]["active"] is True
    # Written from the stage, not the status change's own wording (D41).
    assert [u["label"] for u in payload["updates"]] == ["Moved to treatment"]
    assert payload["coverage"] == {"confirmed": True, "limits": None}
    assert payload["treatment_activity"] is None
    bills = {
        _fact(seeded, k, ORTHO_ID).id for k in (FactKind.MEDICAL_BILL, FactKind.LIEN)
    }
    assert {b["fact_id"] for b in payload["bills"]} == bills
    assert all(b["amount_cents"] and b["has_source"] for b in payload["bills"])
    assert [r["has_source"] for r in payload["records"]] == [True]
    # The task that raised the record request is the same ask, listed once.
    assert [r["fact_id"] for r in payload["requests"]] == [
        _fact(seeded, FactKind.RECORD_REQUEST, ORTHO_ID).id
    ]


def test_payload_carries_nothing_internal(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    every_setting = dict.fromkeys(
        ["case_stage", "coverage_exists", "coverage_limits", "own_bills"]
        + ["own_records", "requests", "treatment_activity"],
        True,
    )
    share = _create(client, user_id, settings=every_setting)
    text = json.dumps(_ok(client.get(f"/api/p/{_token(share)}")))

    withheld = [
        f
        for f in seeded.scalars(select(Fact))
        if f.kind not in SETTING_BY_KIND
        or f.visibility is Visibility.INTERNAL
        or f.mentions_strategy
        or (f.provider_contact_id not in (None, ORTHO_ID))
    ]
    assert withheld
    for fact in withheld:
        assert f'"fact_id": {fact.id},' not in text
        assert fact.title not in text
    # Case-level titles can paraphrase internal notes; only neutral labels go out.
    for fact in seeded.scalars(select(Fact).where(Fact.kind == FactKind.POLICY_LIMIT)):
        assert fact.title not in text


def test_preview_is_the_provider_payload_plus_hide_controls(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    bill = _fact(seeded, FactKind.MEDICAL_BILL, ORTHO_ID)
    share = _create(client, user_id, hidden_fact_ids=[bill.id])

    preview = _ok(client.get(f"/api/shares/{share['id']}/preview"))
    provider = _ok(client.get(f"/api/p/{_token(share)}"))

    assert preview["payload"] == provider
    assert bill.id not in {b["fact_id"] for b in provider["bills"]}
    hidden = {i["fact_id"]: i["hidden"] for i in preview["items"]}
    assert hidden[bill.id] is True
    assert sum(hidden.values()) == 1
    # Previewing is not the provider opening the link.
    [listed] = _ok(client.get(f"/api/matters/{MATTER_ID}/shares"))
    assert listed["opened_count"] == 1


def test_patch_changes_only_the_fields_sent(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    share = _create(client, user_id, note="Please send the updated records.")

    patched = _ok(
        client.patch(
            f"/api/shares/{share['id']}",
            json={"settings": {"own_bills": False, "treatment_activity": True}},
        )
    )
    assert patched["note"] == "Please send the updated records."
    payload = _ok(client.get(f"/api/p/{_token(share)}"))
    assert payload["bills"] is None
    assert payload["treatment_activity"]["last_visit_month"]
    assert payload["note"] == "Please send the updated records."

    cleared = _ok(client.patch(f"/api/shares/{share['id']}", json={"note": None}))
    assert cleared["note"] is None
    assert cleared["settings"]["treatment_activity"] is True


def test_naive_expiry_is_rejected(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    share = _create(client, user_id)
    response = client.patch(
        f"/api/shares/{share['id']}", json={"expires_at": "2030-01-01T00:00:00"}
    )
    assert response.status_code == 422


def test_revoked_link_is_gone_everywhere(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    share = _create(client, user_id)
    token = _token(share)
    bill = _fact(seeded, FactKind.MEDICAL_BILL, ORTHO_ID)

    revoked = _ok(client.post(f"/api/shares/{share['id']}/revoke"))
    assert revoked["revoked_at"] is not None
    again = _ok(client.post(f"/api/shares/{share['id']}/revoke"))
    assert again["revoked_at"] == revoked["revoked_at"]

    assert client.get(f"/api/p/{token}").status_code == 410
    assert client.get(f"/api/p/{token}/facts/{bill.id}/source").status_code == 410
    assert client.get(f"/api/shares/{share['id']}/preview").status_code == 410
    assert (
        client.patch(f"/api/shares/{share['id']}", json={"note": "x"}).status_code
        == 409
    )
    [listed] = _ok(client.get(f"/api/matters/{MATTER_ID}/shares"))
    assert listed["opened_count"] == 0


def test_expired_link_is_gone(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    share = _create(client, user_id)
    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    _ok(client.patch(f"/api/shares/{share['id']}", json={"expires_at": past}))

    assert client.get(f"/api/p/{_token(share)}").status_code == 410


def test_unknown_token_is_404(seeded: Session, client: TestClient) -> None:
    assert client.get("/api/p/not-a-real-token").status_code == 404


def test_create_needs_a_known_user_and_a_medical_provider(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    url = f"/api/matters/{MATTER_ID}/shares"
    body = {"provider_contact_id": ORTHO_ID}
    assert client.post(url, json=body).status_code == 422
    assert client.post(url, json=body, headers={"X-User-Id": "999"}).status_code == 401
    for contact in (CLIENT_ID, INSURER_ID):
        response = client.post(
            url,
            json={"provider_contact_id": contact},
            headers={"X-User-Id": str(user_id)},
        )
        assert response.status_code == 422
    headers = {"X-User-Id": str(user_id)}
    assert (
        client.post("/api/matters/999/shares", json=body, headers=headers).status_code
        == 404
    )


def test_provider_opens_only_the_cited_pages_of_their_own_documents(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    ortho = _token(_create(client, user_id, ORTHO_ID))
    therapy = _token(_create(client, user_id, THERAPY_ID))
    ortho_bill = _fact(seeded, FactKind.MEDICAL_BILL, ORTHO_ID)
    therapy_bill = _fact(seeded, FactKind.MEDICAL_BILL, THERAPY_ID)
    coverage = _fact(seeded, FactKind.COVERAGE, None)

    source = _ok(client.get(f"/api/p/{ortho}/facts/{ortho_bill.id}/source"))
    assert source["quote"] == ortho_bill.quote
    assert source["page"]["page_no"] == ortho_bill.page_no
    image = client.get(source["page"]["image_url"])
    assert image.status_code == 200
    assert image.headers["content-type"] == "image/png"

    # Another provider's bill, a case-level fact, and an emailed bill have no source here.
    assert (
        client.get(f"/api/p/{therapy}/facts/{ortho_bill.id}/source").status_code == 404
    )
    assert client.get(f"/api/p/{ortho}/facts/{coverage.id}/source").status_code == 404
    assert (
        client.get(f"/api/p/{therapy}/facts/{therapy_bill.id}/source").status_code
        == 404
    )
    page_id = source["page"]["page_id"]
    assert client.get(f"/api/p/{therapy}/pages/{page_id}/image").status_code == 404

    # A hidden bill's source closes with it.
    hidden = _token(_create(client, user_id, hidden_fact_ids=[ortho_bill.id]))
    assert (
        client.get(f"/api/p/{hidden}/facts/{ortho_bill.id}/source").status_code == 404
    )


def _providers(client: TestClient) -> dict[int, dict[str, Any]]:
    rows = _ok(client.get(f"/api/matters/{MATTER_ID}/providers"))
    return {row["contact_id"]: row for row in rows}


def test_providers_panel_totals_and_share_status(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    rows = _providers(client)

    # Only contacts the field mapping calls medical providers; never the client or insurer.
    assert set(rows) == {ORTHO_ID, THERAPY_ID}
    ortho, therapy = rows[ORTHO_ID], rows[THERAPY_ID]
    assert ortho["role_label"] and therapy["role_label"]
    # Bills only: a lien on the same charges is not billed twice.
    assert (ortho["billed_cents"], therapy["billed_cents"]) == (248_000, 96_000)
    assert (ortho["records_received"], therapy["records_received"]) == (1, 0)
    assert (ortho["open_requests"], therapy["open_requests"]) == (1, 0)
    assert ortho["share"] is None

    share = _create(client, user_id)
    _ok(client.get(f"/api/p/{_token(share)}"))
    status = _providers(client)[ORTHO_ID]["share"]
    assert status["share_id"] == share["id"]
    assert status["opened_count"] == 1
    assert status["revoked"] is False

    _ok(client.post(f"/api/shares/{share['id']}/revoke"))
    assert _providers(client)[ORTHO_ID]["share"]["revoked"] is True

    # A new live link takes precedence over the withdrawn one.
    newer = _create(client, user_id)
    assert _providers(client)[ORTHO_ID]["share"]["share_id"] == newer["id"]


def test_draft_preview_matches_the_link_it_creates_and_saves_nothing(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    bill = _fact(seeded, FactKind.MEDICAL_BILL, ORTHO_ID)
    body = {
        "provider_contact_id": ORTHO_ID,
        "settings": {"own_records": False, "treatment_activity": True},
        "hidden_fact_ids": [bill.id],
        "note": "Please send the updated records.",
    }
    draft = _ok(client.post(f"/api/matters/{MATTER_ID}/shares/preview", json=body))
    assert _ok(client.get(f"/api/matters/{MATTER_ID}/shares")) == []

    share = _ok(
        client.post(
            f"/api/matters/{MATTER_ID}/shares",
            json=body,
            headers={"X-User-Id": str(user_id)},
        ),
        201,
    )
    assert draft["payload"] == _ok(client.get(f"/api/p/{_token(share)}"))
    assert draft["payload"]["records"] is None
    assert {i["fact_id"] for i in draft["items"] if i["hidden"]} == {bill.id}

    insurer = {"provider_contact_id": INSURER_ID}
    response = client.post(f"/api/matters/{MATTER_ID}/shares/preview", json=insurer)
    assert response.status_code == 422


# --- The note lock, enforced by the server (rule 4, D25) ------------------------------


def _offer_sentence(session: Session) -> str:
    offer = _fact(session, FactKind.OFFER, None)
    return f"The insurer offered ${offer.value_json['amount_cents'] // 100:,}."


def _limit_sentence(session: Session) -> str:
    limit = session.scalars(
        select(Fact).where(Fact.kind == FactKind.POLICY_LIMIT, Fact.origin != "code")
    ).first()
    assert limit is not None
    return (
        f"The per-person policy limit is ${limit.value_json['amount_cents'] // 100:,}."
    )


def test_a_note_that_discloses_an_internal_figure_is_refused(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    response = client.post(
        f"/api/matters/{MATTER_ID}/shares",
        json={"provider_contact_id": ORTHO_ID, "note": _offer_sentence(seeded)},
        headers={"X-User-Id": str(user_id)},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    [locked] = detail["locked"]
    assert locked["verdict"] == "do_not_send" and locked["text"].startswith("$")
    assert client.get(f"/api/matters/{MATTER_ID}/shares").json() == []


def test_changing_the_note_to_a_locked_one_changes_nothing(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    share = _create(client, user_id, note="Thank you for the records.")

    response = client.patch(
        f"/api/shares/{share['id']}", json={"note": _offer_sentence(seeded)}
    )

    assert response.status_code == 422
    [stored] = client.get(f"/api/matters/{MATTER_ID}/shares").json()
    assert stored["note"] == "Thank you for the records."


def test_turning_off_what_a_note_relies_on_is_refused(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    on = {"coverage_limits": True}
    share = _create(client, user_id, settings=on, note=_limit_sentence(seeded))

    response = client.patch(
        f"/api/shares/{share['id']}", json={"settings": {"coverage_limits": False}}
    )

    assert response.status_code == 422
    [stored] = client.get(f"/api/matters/{MATTER_ID}/shares").json()
    assert stored["settings"]["coverage_limits"] is True


def test_a_stored_note_that_is_locked_is_never_served(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    share = _create(client, user_id, note="Thank you for the records.")
    # A share stored before the server checked notes.
    stored = seeded.get(Share, share["id"])
    assert stored is not None
    stored.note = _offer_sentence(seeded)
    seeded.commit()

    served = _ok(client.get(f"/api/p/{_token(share)}"))
    preview = _ok(client.get(f"/api/shares/{share['id']}/preview"))["payload"]

    assert served["note"] is None and preview["note"] is None


def test_a_note_with_nothing_internal_is_served(
    seeded: Session, client: TestClient, user_id: int
) -> None:
    share = _create(client, user_id, note="Thank you for the records.")

    assert _ok(client.get(f"/api/p/{_token(share)}"))["note"] == (
        "Thank you for the records."
    )
