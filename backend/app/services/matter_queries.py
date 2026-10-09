"""Read queries behind the firm view: matter list, header, action board, feed, key
events, timeline."""

import re
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import DigestRun, Fact, FactKind, Source, SourceType, SyncRun
from app.schemas import (
    ActionsOut,
    CaseStagePayload,
    ClientOut,
    DatedFactOut,
    DeadlinePayload,
    FactOut,
    IncidentAccountOut,
    MatterHeaderOut,
    MatterSummaryOut,
    RunOut,
    StageOut,
    TaskPayload,
)
from app.services import brief_view
from app.services.clio_records import RawContact, RawMatter
from app.services.fact_views import (
    deadline_status,
    fact_out,
    fact_ref,
    renderable_facts,
)
from app.services.incident import incident_account, incident_fact
from app.services.kpis import kpi_tiles
from app.services.record_requests import outstanding_record_requests
from app.services.restatements import group_restatements, one_per_record
from app.services.shares import medical_provider_ids

# How many candidates the feed reads per row it returns, to find restatements.
FEED_CANDIDATES_PER_ROW = 10
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


class MatterNotFound(LookupError):
    pass


def _matter_source(session: Session, matter_id: int) -> Source | None:
    return session.scalars(
        select(Source).where(
            Source.matter_id == matter_id, Source.clio_type == SourceType.MATTER
        )
    ).first()


def matter_exists(session: Session, matter_id: int) -> bool:
    return _matter_source(session, matter_id) is not None


def list_matters(session: Session) -> list[MatterSummaryOut]:
    sources = session.scalars(
        select(Source)
        .where(Source.clio_type == SourceType.MATTER)
        .order_by(Source.synced_at.desc())
    )
    matters = []
    for source in sources:
        raw = RawMatter.model_validate(source.raw_json)
        matters.append(
            MatterSummaryOut(
                matter_id=source.matter_id,
                display_number=raw.display_number,
                description=raw.description,
                client_name=raw.client.name if raw.client else None,
                synced_at=source.synced_at,
            )
        )
    return matters


def _latest_run(
    session: Session, model: type[SyncRun] | type[DigestRun], matter_id: int
) -> RunOut | None:
    run = session.scalars(
        select(model)
        .where(model.matter_id == matter_id)
        .order_by(model.started_at.desc())
    ).first()
    if run is None:
        return None
    return RunOut(
        id=run.id,
        started_at=run.started_at,
        finished_at=run.finished_at,
        error=run.error,
        stats=run.stats_json,
    )


def _client(session: Session, matter_id: int, raw: RawMatter) -> ClientOut | None:
    if raw.client is None or raw.client.name is None:
        return None
    contact_id = int(raw.client.id) if raw.client.id is not None else None
    contact = session.scalars(
        select(Source).where(
            Source.matter_id == matter_id,
            Source.clio_type == SourceType.CONTACT,
            Source.clio_id == str(contact_id),
        )
    ).first()
    avatar = RawContact.model_validate(contact.raw_json).avatar if contact else None
    return ClientOut(
        contact_id=contact_id,
        name=raw.client.name,
        avatar_url=avatar.url if avatar else None,
    )


def _best(facts: list[Fact]) -> Fact | None:
    """The most recent fact, breaking ties by significance."""
    return max(
        facts,
        key=lambda f: (f.event_date or date.min, f.significance),
        default=None,
    )


def _dated(fact: Fact | None) -> DatedFactOut | None:
    if fact is None or fact.event_date is None:
        return None
    return DatedFactOut(on=fact.event_date, fact=fact_ref(fact))


def _account(group: list[Fact]) -> IncidentAccountOut | None:
    if not group:
        return None
    group = one_per_record(group)
    return IncidentAccountOut(
        text=group[0].title,
        fact=fact_ref(group[0]),
        restated_by=[fact_ref(f) for f in group[1:]],
    )


def _stage(session: Session, matter_id: int, facts: list[Fact]) -> StageOut:
    """The stage from Clio's own stage fact, else the brief's, labelled as inferred.

    Without a cited fact there is no stage on screen: a label without a source is a guess.
    """
    fact = _best(facts)
    if fact is None:
        try:
            brief = brief_view.matter_brief(session, matter_id)
        except brief_view.BriefNotFound:
            brief = None
        if brief is None or not brief.stage_facts:
            return StageOut(stage=None, label=None, inferred=False, facts=[])
        return StageOut(
            stage=brief.stage, label=None, inferred=True, facts=brief.stage_facts
        )
    payload = CaseStagePayload.model_validate(fact.value_json)
    return StageOut(
        stage=payload.stage,
        label=fact.title,
        inferred=payload.inferred,
        facts=[fact_ref(fact)],
    )


def matter_header(session: Session, matter_id: int) -> MatterHeaderOut:
    source = _matter_source(session, matter_id)
    if source is None:
        raise MatterNotFound(f"matter {matter_id} has not been synced")
    raw = RawMatter.model_validate(source.raw_json)
    facts = session.scalars(renderable_facts(matter_id)).all()
    by_kind: dict[FactKind, list[Fact]] = {kind: [] for kind in FactKind}
    for fact in facts:
        by_kind[fact.kind].append(fact)
    return MatterHeaderOut(
        matter_id=matter_id,
        display_number=raw.display_number,
        description=raw.description,
        client=_client(session, matter_id, raw),
        responsible_attorney=raw.responsible_attorney.name
        if raw.responsible_attorney
        else None,
        opened_on=raw.open_date,
        stage=_stage(session, matter_id, by_kind[FactKind.CASE_STAGE]),
        incident=_dated(incident_fact(by_kind[FactKind.INCIDENT])),
        incident_account=_account(incident_account(by_kind[FactKind.INCIDENT])),
        last_client_contact=_dated(_best(by_kind[FactKind.CLIENT_CONTACT])),
        kpis=kpi_tiles(by_kind),
        digested=bool(facts),
        last_sync=_latest_run(session, SyncRun, matter_id),
        last_digest=_latest_run(session, DigestRun, matter_id),
    )


def _due_date(fact: Fact) -> date | None:
    """The day an item is due, as written: no time-zone shift of the calendar day."""
    due_at = None
    if fact.kind is FactKind.TASK:
        due_at = TaskPayload.model_validate(fact.value_json).due_at
    elif fact.kind is FactKind.DEADLINE:
        due_at = DeadlinePayload.model_validate(fact.value_json).due_at
    return due_at.date() if due_at else fact.event_date


def _by_due(facts: list[Fact]) -> list[FactOut]:
    ordered = sorted(facts, key=lambda f: _due_date(f) or date.max)
    return [fact_out(f) for f in ordered]


def matter_actions(session: Session, matter_id: int, today: date) -> ActionsOut:
    """Split open work into overdue, upcoming, and waiting on others.

    The groups do not overlap: overdue wins, then waiting, then upcoming. A record
    request raised by a task already on the board is not listed twice, and a request
    the provider has answered is not listed (`record_requests.py`). Past calendar
    entries are not overdue; they happened. A deadline whose Clio task is complete
    has been met, so it is not upcoming either.
    """
    kinds = (
        FactKind.TASK,
        FactKind.DEADLINE,
        FactKind.RECORD_REQUEST,
        FactKind.RECORDS_RECEIVED,  # to tell which requests are answered
    )
    facts = list(
        session.scalars(renderable_facts(matter_id).where(Fact.kind.in_(kinds)))
    )
    task_sources = {f.source_id for f in facts if f.kind is FactKind.TASK}
    outstanding = {f.id for f in outstanding_record_requests(facts)}
    overdue: list[Fact] = []
    upcoming: list[Fact] = []
    waiting: list[Fact] = []
    for fact in facts:
        if fact.kind is FactKind.RECORDS_RECEIVED:
            continue
        if fact.kind is FactKind.RECORD_REQUEST:
            if fact.id in outstanding and fact.source_id not in task_sources:
                waiting.append(fact)
            continue
        due = _due_date(fact)
        if fact.kind is FactKind.DEADLINE:
            # A deadline whose Clio task is complete has been met: nothing is due.
            met = deadline_status(fact) == "complete"
            if due is not None and due >= today and not met:
                upcoming.append(fact)
            continue
        task = TaskPayload.model_validate(fact.value_json)
        if task.status != "open":
            continue
        if due is not None and due < today:
            overdue.append(fact)
        elif task.waiting_on not in (None, "firm"):
            waiting.append(fact)
        elif due is not None:
            upcoming.append(fact)
    return ActionsOut(
        overdue=_by_due(overdue),
        upcoming=_by_due(upcoming),
        waiting_on_others=_by_due(waiting),
    )


def matter_feed(session: Session, matter_id: int, limit: int) -> list[FactOut]:
    """The most significant facts, each once, citing the records that restate it.

    Restatements are looked for among the leading candidates only, which is where a
    fact restated across many records lands.
    """
    candidates = list(
        session.scalars(
            renderable_facts(matter_id)
            .order_by(
                Fact.significance.desc(), Fact.event_date.desc().nulls_last(), Fact.id
            )
            .limit(limit * FEED_CANDIDATES_PER_ROW)
        )
    )
    return [_with_restatements(g) for g in group_restatements(candidates)[:limit]]


def _with_restatements(group: list[Fact]) -> FactOut:
    """The group's lead fact, citing the other records that restate it, one fact each."""
    group = one_per_record(group)
    return fact_out(group[0]).model_copy(
        update={"restated_by": [fact_ref(f) for f in group[1:]]}
    )


def matter_key_events(
    session: Session, matter_id: int, today: date, limit: int
) -> list[FactOut]:
    """What has happened on the case, oldest first: the incident, then the most
    significant past events, each once, at most `KEY_EVENTS_PER_KIND` of a kind.

    The incident is one row: the header's account of it, citing the records that give
    it, else the fact the header cites. Hundreds of incident facts can share one day in
    different words, and those do not fold into one row. Each kind gets its own
    candidate window, since one window over every kind fills with the most numerous
    kind and leaves the others out.
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
    leaders: list[list[Fact]] = []
    for kind in KEY_EVENT_KINDS:
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
        leaders.extend(group_restatements(list(candidates))[:KEY_EVENTS_PER_KIND])
    leaders.sort(
        key=lambda g: (-g[0].significance, -_ordinal(g[0].event_date), g[0].id)
    )
    chosen = pinned + leaders[: max(limit - len(pinned), 0)]
    chosen.sort(key=lambda g: (_ordinal(g[0].event_date), g[0].id))
    return [_with_restatements(group) for group in chosen]


def _ordinal(day: date | None) -> int:
    return day.toordinal() if day else 0


def matter_timeline(
    session: Session, matter_id: int, kind: FactKind | None, text: str | None
) -> list[FactOut]:
    query = renderable_facts(matter_id)
    if kind is not None:
        query = query.where(Fact.kind == kind)
    if text:
        # SQL narrows by substring; the regex below keeps only word-start matches.
        query = query.where(
            or_(
                Fact.title.icontains(text, autoescape=True),
                Fact.quote.icontains(text, autoescape=True),
            )
        )
    facts = session.scalars(
        query.order_by(Fact.event_date.desc().nulls_last(), Fact.id.desc())
    ).all()
    if text:
        # "lien" should find liens, not every mention of a client.
        word_start = re.compile(rf"\b{re.escape(text)}", re.IGNORECASE)
        facts = [f for f in facts if word_start.search(f"{f.title}\n{f.quote or ''}")]
    return [fact_out(f) for f in facts]


def matter_injuries(session: Session, matter_id: int) -> list[FactOut]:
    """Injuries and diagnoses: those the client's treating providers recorded first,
    then the rest (defense exams, expert reviews, notes, pleadings), each part most
    significant first.

    No synced field marks a defense exam; what the data does say is which facts come
    from one of the matter's treating providers (the field mapping's roles).
    """
    treating = medical_provider_ids(session, matter_id)
    facts = session.scalars(
        renderable_facts(matter_id)
        .where(Fact.kind.in_((FactKind.INJURY, FactKind.DIAGNOSIS)))
        .order_by(
            Fact.significance.desc(), Fact.event_date.desc().nulls_last(), Fact.id
        )
    )
    ordered = sorted(facts, key=lambda f: f.provider_contact_id not in treating)
    return [fact_out(f) for f in ordered]
