"""Cross-checks put the firm's own figures beside what the documents say.

The specials figure was checked against the bills; the policy limit the firm entered
on the matter was never checked against the limits the documents state.
"""

from pathlib import Path

from sqlalchemy.orm import Session

from app.digest.cross_check import cross_check
from app.models import Confidence, Fact, FactKind, Origin, Source, SourceType

MATTER = 3


def _source(session: Session, kind: SourceType, clio_id: str) -> Source:
    source = Source(matter_id=MATTER, clio_type=kind, clio_id=clio_id, raw_json={})
    session.add(source)
    session.flush()
    return source


def _limit(
    session: Session,
    source: Source,
    dollars: int,
    per: str | None,
    page_no: int | None = None,
) -> Fact:
    fact = Fact(
        matter_id=MATTER,
        kind=FactKind.POLICY_LIMIT,
        title="Invented limit",
        value_json={"amount_cents": dollars * 100, "per": per},
        source_id=source.id,
        page_no=page_no,
        quote="Invented quote",
        confidence=Confidence.HIGH,
        origin=Origin.MODEL,
    )
    session.add(fact)
    session.flush()
    return fact


def test_a_firm_limit_the_documents_contradict_carries_their_value(
    data_dir: Path, session: Session
) -> None:
    matter = _source(session, SourceType.MATTER, "m")
    letter = _source(session, SourceType.DOCUMENT, "d")
    firm = _limit(session, matter, 40_000, "person")
    _limit(session, letter, 70_000, "person", page_no=2)
    _limit(session, letter, 90_000, "occurrence", page_no=2)

    assert cross_check(session, MATTER) == 1

    assert firm.value_json["alt_values"] == [
        {"amount_cents": 7_000_000, "source_id": letter.id, "page_no": 2}
    ]


def test_a_firm_limit_one_document_confirms_is_not_flagged(
    data_dir: Path, session: Session
) -> None:
    matter = _source(session, SourceType.MATTER, "m")
    letter = _source(session, SourceType.DOCUMENT, "d")
    note = _source(session, SourceType.NOTE, "n")
    firm = _limit(session, matter, 40_000, "person")
    _limit(session, letter, 40_000, "person", page_no=1)
    # A second policy named elsewhere in the file is not a contradiction.
    _limit(session, note, 70_000, "person")

    assert cross_check(session, MATTER) == 0
    assert firm.value_json["alt_values"] == []


def test_a_document_limit_is_not_checked_against_itself(
    data_dir: Path, session: Session
) -> None:
    letter = _source(session, SourceType.DOCUMENT, "d")
    other = _source(session, SourceType.DOCUMENT, "e")
    first = _limit(session, letter, 40_000, "person", page_no=1)
    _limit(session, other, 70_000, "person", page_no=1)

    assert cross_check(session, MATTER) == 0
    assert first.value_json.get("alt_values") in (None, [])
