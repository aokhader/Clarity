"""Read queries behind the firm view: matter list, header, action board, feed, timeline."""

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
    MatterHeaderOut,
    MatterSummaryOut,
    RecordRequestPayload,
    RunOut,
    StageOut,
    TaskPayload,
)
from app.services.clio_records import RawContact, RawMatter
from app.services.fact_views import fact_out, fact_ref, renderable_facts
from app.services.kpis import kpi_tiles


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


def _stage(facts: list[Fact]) -> StageOut:
    fact = _best(facts)
    if fact is None:
        # No stage fact means no stage on screen: a label without a source is a guess.
        return StageOut(stage=None, label=None, inferred=False, facts=[])
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
        stage=_stage(by_kind[FactKind.CASE_STAGE]),
        incident=_dated(_best(by_kind[FactKind.INCIDENT])),
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
    request raised by a task already on the board is not listed twice. Past calendar
    entries are not overdue; they happened.
    """
    kinds = (FactKind.TASK, FactKind.DEADLINE, FactKind.RECORD_REQUEST)
    facts = session.scalars(
        renderable_facts(matter_id).where(Fact.kind.in_(kinds))
    ).all()
    task_sources = {f.source_id for f in facts if f.kind is FactKind.TASK}
    overdue: list[Fact] = []
    upcoming: list[Fact] = []
    waiting: list[Fact] = []
    for fact in facts:
        if fact.kind is FactKind.RECORD_REQUEST:
            request = RecordRequestPayload.model_validate(fact.value_json)
            if request.status == "open" and fact.source_id not in task_sources:
                waiting.append(fact)
            continue
        due = _due_date(fact)
        if fact.kind is FactKind.DEADLINE:
            if due is not None and due >= today:
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
    facts = session.scalars(
        renderable_facts(matter_id)
        .order_by(
            Fact.significance.desc(), Fact.event_date.desc().nulls_last(), Fact.id
        )
        .limit(limit)
    )
    return [fact_out(f) for f in facts]


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
