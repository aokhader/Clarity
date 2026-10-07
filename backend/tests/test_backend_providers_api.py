"""The providers panel says "no bills on file" rather than $0 (D16, critic finding 15)."""

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Fact, FactKind
from tests.fixtures.synthetic_matter import MATTER_ID, ORTHO_ID, THERAPY_ID


def _billed(client: TestClient) -> dict[int, int | None]:
    rows = client.get(f"/api/matters/{MATTER_ID}/providers").json()
    return {row["contact_id"]: row["billed_cents"] for row in rows}


def test_a_provider_with_no_bill_on_file_has_no_billed_total(
    seeded: Session, client: TestClient
) -> None:
    for bill in seeded.scalars(
        select(Fact).where(
            Fact.kind == FactKind.MEDICAL_BILL, Fact.provider_contact_id == THERAPY_ID
        )
    ):
        seeded.delete(bill)
    seeded.commit()

    billed = _billed(client)

    assert billed[THERAPY_ID] is None
    assert billed[ORTHO_ID]


def test_a_bill_with_no_amount_is_not_a_total_of_zero(
    seeded: Session, client: TestClient
) -> None:
    for bill in seeded.scalars(
        select(Fact).where(
            Fact.kind == FactKind.MEDICAL_BILL, Fact.provider_contact_id == THERAPY_ID
        )
    ):
        bill.value_json = {**bill.value_json, "amount_cents": None}
    seeded.commit()

    assert _billed(client)[THERAPY_ID] is None
