"""The story so far: what has happened on a matter, oldest first, each event once.

The incident leads, then the court events, then the most significant other events
(D41, D43).
"""

from datetime import date

from sqlalchemy.orm import Session

from app.models import Fact, FactKind
from app.schemas import FactOut, LitigationEventPayload
from app.services.fact_views import renderable_facts, with_restatements
from app.services.incident import incident_account, incident_fact
from app.services.matter_queries import FEED_CANDIDATES_PER_ROW
from app.services.restatements import group_restatements

# At most this many key events of one kind, so one busy kind cannot fill the list.
KEY_EVENTS_PER_KIND = 3
# What has happened on a case. Tasks, call notes, liability opinions and the kinds
# that state where things stand (stage, limits, value, bills, parties) are not events,
# and neither are deadlines: a date set for a hearing or a surgery does not say that
# it took place.
KEY_EVENT_KINDS = (
    FactKind.DIAGNOSIS,
    FactKind.TREATMENT_VISIT,
    FactKind.STATUS_CHANGE,
    FactKind.COVERAGE,
    FactKind.DEMAND,
    FactKind.OFFER,
    FactKind.SETTLEMENT,
    FactKind.RECORDS_RECEIVED,
    FactKind.LITIGATION_EVENT,
)
# The court events that tell where a suit stands, in the order they are chosen (D43):
# a filing, a dismissal and a refiling outrank an exchange of papers, whatever the
# scores. Every other event type comes after these.
COURT_EVENT_ORDER = ("filed", "dismissed", "renewed", "answered")


def matter_key_events(
    session: Session, matter_id: int, today: date, limit: int
) -> list[FactOut]:
    """What has happened on the case, oldest first: the incident and up to
    `KEY_EVENTS_PER_KIND` court events, pinned, then the most significant other past
    events, each once, at most `KEY_EVENTS_PER_KIND` of a kind.

    The incident is one row: the header's account of it, citing the records that give
    it, else the fact the header cites. Hundreds of incident facts can share one day in
    different words, and those do not fold into one row. Each kind gets its own
    candidate window, since one window over every kind fills with the most numerous
    kind and leaves the others out. When the limit is smaller than what is pinned, the
    incident stays, then the court events in their order.
    """
    incidents = list(
        session.scalars(
            renderable_facts(matter_id).where(Fact.kind == FactKind.INCIDENT)
        )
    )
    cited = incident_fact(incidents)
    incident = incident_account(incidents) or ([cited] if cited else [])
    pinned: list[list[Fact]] = []
    if incident and incident[0].event_date and incident[0].event_date <= today:
        pinned = [incident]
    pinned += _court_events(session, matter_id, today)
    leaders = [
        group
        for kind in KEY_EVENT_KINDS
        if kind is not FactKind.LITIGATION_EVENT
        for group in _leading_events(session, matter_id, kind, today)
    ]
    leaders.sort(
        key=lambda g: (-g[0].significance, -_ordinal(g[0].event_date), g[0].id)
    )
    chosen = (pinned + leaders)[:limit]
    chosen.sort(key=lambda g: (_ordinal(g[0].event_date), g[0].id))
    return [with_restatements(group) for group in chosen]


def _court_events(session: Session, matter_id: int, today: date) -> list[list[Fact]]:
    """The dated past court events to pin, in `COURT_EVENT_ORDER` then by significance,
    restatements folded, at most `KEY_EVENTS_PER_KIND`. All are read, since a filing of
    low significance must still outrank the rest; a matter has few court events."""
    candidates = session.scalars(
        renderable_facts(matter_id).where(
            Fact.kind == FactKind.LITIGATION_EVENT,
            Fact.event_date.is_not(None),
            Fact.event_date <= today,
        )
    )
    ordered = sorted(candidates, key=_court_order)
    return group_restatements(ordered)[:KEY_EVENTS_PER_KIND]


def _court_order(fact: Fact) -> tuple[int, int, int, int]:
    event = LitigationEventPayload.model_validate(fact.value_json).event
    rank = (
        COURT_EVENT_ORDER.index(event)
        if event in COURT_EVENT_ORDER
        else len(COURT_EVENT_ORDER)
    )
    return (rank, -fact.significance, -_ordinal(fact.event_date), fact.id)


def _leading_events(
    session: Session, matter_id: int, kind: FactKind, today: date
) -> list[list[Fact]]:
    """A kind's most significant dated past events, restatements folded, at most
    `KEY_EVENTS_PER_KIND`, most significant first."""
    candidates = session.scalars(
        renderable_facts(matter_id)
        .where(
            Fact.kind == kind,
            Fact.event_date.is_not(None),
            Fact.event_date <= today,
        )
        .order_by(Fact.significance.desc(), Fact.event_date.desc(), Fact.id)
        .limit(KEY_EVENTS_PER_KIND * FEED_CANDIDATES_PER_ROW)
    )
    return group_restatements(list(candidates))[:KEY_EVENTS_PER_KIND]


def _ordinal(day: date | None) -> int:
    return day.toordinal() if day else 0
