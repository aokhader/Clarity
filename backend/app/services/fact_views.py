"""The one query every firm view starts from, and the fact serializers they share."""

from typing import Any, Literal

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.orm import contains_eager, object_session

from app.models import Fact, FactKind, Source, SourceType
from app.schemas import FactOut, FactRef, TaskPayload
from app.services.restatements import one_per_record


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


def deadline_status(fact: Fact) -> Literal["open", "complete"] | None:
    """The status of the Clio task a deadline was read from, taken from the task's own
    fact on the same record.

    The digest stores a task's statute deadline apart from the task and without its
    status, so a statute the firm has met would otherwise read as one that passed.
    """
    if (
        fact.kind is not FactKind.DEADLINE
        or fact.source.clio_type is not SourceType.TASK
    ):
        return None
    session = object_session(fact)
    if session is None:
        return None
    task = session.scalars(
        select(Fact).where(Fact.source_id == fact.source_id, Fact.kind == FactKind.TASK)
    ).first()
    return TaskPayload.model_validate(task.value_json).status if task else None


def _served_value(fact: Fact) -> dict[str, Any]:
    if fact.kind is FactKind.DEADLINE:
        return {**fact.value_json, "status": deadline_status(fact)}
    return fact.value_json


def fact_out(fact: Fact) -> FactOut:
    return FactOut(
        id=fact.id,
        kind=fact.kind,
        title=fact.title,
        event_date=fact.event_date,
        value=_served_value(fact),
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


def with_restatements(group: list[Fact]) -> FactOut:
    """A restatement group's lead fact, citing the other records that restate it, one
    fact each."""
    group = one_per_record(group)
    return fact_out(group[0]).model_copy(
        update={"restated_by": [fact_ref(f) for f in group[1:]]}
    )
