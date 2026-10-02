from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Confidence, Fact, FactKind, Origin, Source, SourceType
from app.services.bills import BillRecord, billed_total_cents, count_bills
from tests.fixtures.synthetic_matter import MATTER_ID, ORTHO_ID

MATTER = 7
PROVIDER = 55
OTHER_PROVIDER = 56


def _source(session: Session, clio_type: SourceType) -> Source:
    source = Source(
        matter_id=MATTER,
        clio_type=clio_type,
        clio_id=f"{clio_type}-{session.query(Source).count()}",
        raw_json={},
    )
    session.add(source)
    session.flush()
    return source


def _bill(
    session: Session,
    clio_type: SourceType,
    amount_cents: int | None,
    provider: int | None = PROVIDER,
    origin: Origin = Origin.MODEL,
) -> Fact:
    fact = Fact(
        matter_id=MATTER,
        kind=FactKind.MEDICAL_BILL,
        title="Charge",
        value_json={"amount_cents": amount_cents},
        source_id=_source(session, clio_type).id,
        page_no=1 if clio_type is SourceType.DOCUMENT else None,
        provider_contact_id=provider,
        confidence=Confidence.HIGH,
        origin=origin,
    )
    session.add(fact)
    session.flush()
    return fact


def _ledger(session: Session, amount_cents: int, provider: int = PROVIDER) -> Fact:
    return _bill(session, SourceType.ACTIVITY, amount_cents, provider, Origin.CODE)


def test_ledger_note_and_itemized_bills_for_the_same_charges_count_once(
    session: Session,
) -> None:
    items = [_bill(session, SourceType.DOCUMENT, cents) for cents in (6_000, 4_000)]
    ledger = _ledger(session, 10_000)
    note = _bill(session, SourceType.NOTE, 10_000)

    [counted] = count_bills([*items, ledger, note])

    assert counted.total_cents == 10_000
    # The itemized bills account for the total and each cites a page, so they are counted.
    assert counted.record is BillRecord.ITEMIZED
    assert counted.facts == items


def test_itemized_bills_that_fall_short_give_way_to_the_ledger(
    session: Session,
) -> None:
    item = _bill(session, SourceType.DOCUMENT, 6_000)
    ledger = _ledger(session, 15_000)

    [counted] = count_bills([item, ledger])

    assert (counted.record, counted.total_cents, counted.facts) == (
        BillRecord.LEDGER,
        15_000,
        [ledger],
    )


def test_itemized_bills_within_rounding_of_the_ledger_are_counted(
    session: Session,
) -> None:
    items = [_bill(session, SourceType.DOCUMENT, cents) for cents in (3_333, 3_333)]
    ledger = _ledger(session, 6_700)

    [counted] = count_bills([*items, ledger])

    assert (counted.record, counted.total_cents) == (BillRecord.ITEMIZED, 6_666)


def test_a_total_repeated_in_several_notes_is_one_bill(session: Session) -> None:
    notes = [_bill(session, SourceType.NOTE, 25_000) for _ in range(3)]

    [counted] = count_bills(notes)

    assert (counted.total_cents, counted.facts) == (25_000, notes[:1])


def test_providers_are_counted_separately_and_added(session: Session) -> None:
    bills = [
        _bill(session, SourceType.DOCUMENT, 10_000),
        _ledger(session, 10_000),
        _bill(session, SourceType.DOCUMENT, 7_000, provider=OTHER_PROVIDER),
        _bill(session, SourceType.DOCUMENT, 2_000, provider=None),
    ]
    assert billed_total_cents(bills) == 19_000


def test_a_note_restating_a_providers_total_without_naming_it_is_not_added(
    session: Session,
) -> None:
    bills = [
        _bill(session, SourceType.DOCUMENT, 1_450),
        _bill(session, SourceType.NOTE, 1_450, provider=None),
        _bill(session, SourceType.NOTE, 900, provider=None),
    ]
    # The unattributed $14.50 restates the provider's bill; the $9.00 is a bill of its own.
    assert billed_total_cents(bills) == 2_350


def test_bills_without_an_amount_and_other_kinds_are_not_counted(
    session: Session,
) -> None:
    unpriced = _bill(session, SourceType.DOCUMENT, None)
    lien = _bill(session, SourceType.DOCUMENT, 9_000)
    lien.kind = FactKind.LIEN

    assert count_bills([unpriced, lien]) == []
    assert billed_total_cents([unpriced, lien]) == 0


def _preview(client: TestClient, provider: int) -> dict[str, Any]:
    response = client.post(
        f"/api/matters/{MATTER_ID}/shares/preview",
        json={"provider_contact_id": provider},
    )
    assert response.status_code == 200, response.text
    return response.json()["payload"]


def test_provider_page_totals_bills_without_the_lien_on_the_same_charges(
    seeded: Session, client: TestClient
) -> None:
    payload = _preview(client, ORTHO_ID)

    assert payload["bills_total"] == {"amount_cents": 248_000, "bill_count": 1}
    # The lien stays listed for the office to see, but is not added to what it billed.
    assert len(payload["bills"]) == 2
