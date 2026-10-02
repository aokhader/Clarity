"""The one query every firm view starts from, and the fact serializers they share."""

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.orm import contains_eager

from app.models import Fact, Source, SourceType
from app.schemas import FactOut, FactRef


def renderable_facts(matter_id: int) -> Select[tuple[Fact]]:
    """Facts that may be shown, with their source loaded.

    A document fact without its page and quote is never rendered: an attorney must be
    able to see where every claim came from.
    """
    return (
        select(Fact)
        .join(Fact.source)
        .options(contains_eager(Fact.source))
        .where(
            Fact.matter_id == matter_id,
            or_(
                Source.clio_type != SourceType.DOCUMENT,
                and_(Fact.page_no.is_not(None), Fact.quote.is_not(None)),
            ),
        )
    )


def fact_out(fact: Fact) -> FactOut:
    return FactOut(
        id=fact.id,
        kind=fact.kind,
        title=fact.title,
        event_date=fact.event_date,
        value=fact.value_json,
        source_id=fact.source_id,
        source_type=fact.source.clio_type,
        page_no=fact.page_no,
        quote=fact.quote,
        provider_contact_id=fact.provider_contact_id,
        visibility=fact.visibility,
        significance=fact.significance,
        confidence=fact.confidence,
        verified=fact.verified,
        origin=fact.origin,
        created_at=fact.created_at,
    )


def fact_ref(fact: Fact) -> FactRef:
    return FactRef(
        id=fact.id,
        source_type=fact.source.clio_type,
        page_no=fact.page_no,
        confidence=fact.confidence,
    )
