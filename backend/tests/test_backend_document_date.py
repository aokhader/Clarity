"""A document's own date in the source view, apart from its upload day (finding 13)."""

from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.models import Source, SourceType
from app.services.source_views import source_out

UPLOADED = datetime(2031, 7, 14, 17, 0, tzinfo=UTC)


def _document(session: Session, raw: dict[str, object]) -> Source:
    source = Source(
        matter_id=1,
        clio_type=SourceType.DOCUMENT,
        clio_id=f"doc-{session.query(Source).count()}",
        raw_json={"name": "Itemized statement", **raw},
        clio_created_at=UPLOADED,
    )
    session.add(source)
    session.flush()
    return source


def test_a_document_clio_dates_shows_that_date(session: Session) -> None:
    source = _document(session, {"received_at": "2030-02-03T09:30:00-08:00"})

    out = source_out(session, source)

    assert out.document_date == date(2030, 2, 3)
    assert out.occurred_on == UPLOADED.date()  # unchanged: the upload day


def test_a_document_with_no_date_of_its_own_has_none(session: Session) -> None:
    out = source_out(session, _document(session, {}))

    assert out.document_date is None
    assert out.occurred_on == UPLOADED.date()


def test_a_note_has_no_document_date(session: Session) -> None:
    note = Source(
        matter_id=1,
        clio_type=SourceType.NOTE,
        clio_id="note-1",
        raw_json={"subject": "Call", "detail": "Spoke with the adjuster."},
        clio_created_at=UPLOADED,
    )
    session.add(note)
    session.flush()

    assert source_out(session, note).document_date is None
