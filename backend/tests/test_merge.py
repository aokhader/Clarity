from datetime import date

from sqlalchemy.orm import Session

from app.digest.merge import deduplicate
from app.models import Confidence, Fact, FactKind, Origin, Source, SourceType

MATTER = 7


def _document(session: Session, clio_id: str) -> Source:
    source = Source(
        matter_id=MATTER, clio_type=SourceType.DOCUMENT, clio_id=clio_id, raw_json={}
    )
    session.add(source)
    session.flush()
    return source


def _bill(session: Session, source: Source, provider: int | None) -> Fact:
    fact = Fact(
        matter_id=MATTER,
        kind=FactKind.MEDICAL_BILL,
        title="Office visit charge",
        value_json={"amount_cents": 4000},
        event_date=date(2024, 3, 1),
        source_id=source.id,
        page_no=1,
        quote="Charge: $40.00",
        provider_contact_id=provider,
        confidence=Confidence.HIGH,
        origin=Origin.MODEL,
    )
    session.add(fact)
    session.flush()
    return fact


def test_equal_bills_without_a_provider_in_two_documents_are_both_kept(
    session: Session,
) -> None:
    _bill(session, _document(session, "1"), None)
    _bill(session, _document(session, "2"), None)
    assert deduplicate(session, MATTER) == 0


def test_equal_bills_from_one_provider_are_merged_with_corroboration(
    session: Session,
) -> None:
    first = _document(session, "1")
    second = _document(session, "2")
    keeper = _bill(session, first, 55)
    _bill(session, second, 55)
    assert deduplicate(session, MATTER) == 1
    assert keeper.value_json["corroborating_source_ids"] == [second.id]
