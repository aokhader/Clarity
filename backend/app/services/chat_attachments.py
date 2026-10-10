"""What the user pointed at, resolved inside the matter (D49).

The client sends ids only (docs/chat-contract.md, rule 4). Each is looked up here
inside the matter, so an id from another matter, or a fact that cannot be shown, is
refused rather than trusted. The label is built here from generic words, the item's
kind and a date, so nothing the client typed reaches the model as a label, and no
record text appears in it beyond a provider's name as the providers panel shows it.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.config import get_settings
from app.digest.chat import PageExcerpt
from app.models import Call, Fact, FactKind, Source, SourceType
from app.schemas import (
    AskCallRef,
    AskFactsRef,
    AskKpiRef,
    AskProviderRef,
    AskSourceRef,
    AskStageRef,
)
from app.services.chat_pages import page_excerpts
from app.services.fact_views import renderable_facts
from app.services.kpis import kpi_tiles
from app.services.matter_queries import matter_stage
from app.services.restatements import restatements_of
from app.services.shares import contact_name
from app.services.source_views import source_date

AskRef = (
    AskFactsRef | AskSourceRef | AskProviderRef | AskCallRef | AskKpiRef | AskStageRef
)

# The most facts one item carries (AskItemOut.facts), its own first, then restatements.
MAX_ITEM_FACTS = 50
# The kinds that record the case moving: a stage change, and a court event (D41).
_MOVED_THE_CASE = (FactKind.STATUS_CHANGE, FactKind.LITIGATION_EVENT)

_KIND_WORDS: dict[FactKind, str] = {
    FactKind.CASE_STAGE: "Stage",
    FactKind.STATUS_CHANGE: "Status",
    FactKind.INJURY: "Injury",
    FactKind.DIAGNOSIS: "Diagnosis",
    FactKind.TREATMENT_VISIT: "Treatment",
    FactKind.MEDICAL_BILL: "Bill",
    FactKind.LIEN: "Lien",
    FactKind.RECORDS_RECEIVED: "Records",
    FactKind.RECORD_REQUEST: "Request",
    FactKind.COVERAGE: "Coverage",
    FactKind.POLICY_LIMIT: "Policy limit",
    FactKind.CASE_VALUE: "Value",
    FactKind.LIABILITY: "Liability",
    FactKind.DEMAND: "Demand",
    FactKind.OFFER: "Offer",
    FactKind.SETTLEMENT: "Settlement",
    FactKind.EXPENSE: "Expense",
    FactKind.DEADLINE: "Deadline",
    FactKind.TASK: "Task",
    FactKind.CLIENT_CONTACT: "Client contact",
    FactKind.PARTY: "Party",
    FactKind.INCIDENT: "Incident",
    FactKind.MEDICAL_SPECIALS: "Specials",
    FactKind.ECONOMIC_DAMAGES: "Economic damages",
    FactKind.RECOVERY_CAP: "Recovery cap",
    FactKind.CALL_NOTE: "Call note",
    FactKind.LITIGATION_EVENT: "Litigation",
    FactKind.OTHER: "Record",
}
_SOURCE_WORDS: dict[SourceType, str] = {
    SourceType.MATTER: "Matter record",
    SourceType.CUSTOM_FIELD: "Field",
    SourceType.CONTACT: "Contact",
    SourceType.RELATIONSHIP: "Contact",
    SourceType.NOTE: "Note",
    SourceType.COMMUNICATION: "Email",
    SourceType.TASK: "Task",
    SourceType.CALENDAR_ENTRY: "Calendar entry",
    SourceType.ACTIVITY: "Expense",
    SourceType.DOCUMENT: "Document",
    SourceType.CALL: "Call",
}
_TILE_WORDS = {
    "case_value": "Case value",
    "coverage": "Coverage",
    "medical_specials": "Medical specials",
    "firm_spend": "Firm spend",
}


class ItemNotInMatter(LookupError):
    """An item that does not resolve inside the matter (the route answers 422)."""


@dataclass
class ResolvedItem:
    ref: AskRef
    label: str
    facts: list[Fact]  # renderable, restatements included, at most MAX_ITEM_FACTS
    pages: list[PageExcerpt]


@dataclass
class _Resolved:
    label: str
    facts: list[Fact]


def load_renderable(session: Session, matter_id: int) -> dict[int, Fact]:
    """Every fact of the matter that may be shown, by id, in the header's order."""
    return {f.id: f for f in session.scalars(renderable_facts(matter_id))}


def resolve_items(
    session: Session,
    matter_id: int,
    refs: list[AskRef],
    *,
    renderable: dict[int, Fact] | None = None,
    page_chars: int = 0,
    page_limit: int = 0,
) -> list[ResolvedItem]:
    """Each ref as the facts it stands for, labelled. Page excerpts are built only
    when `page_limit` is above zero (the background run; a request needs none).

    Raises ItemNotInMatter for the first ref that does not resolve in the matter.
    """
    if renderable is None:
        renderable = load_renderable(session, matter_id)
    shown = list(renderable.values())
    items = []
    for ref in refs:
        resolved = _resolve(session, matter_id, ref, renderable)
        pages = (
            page_excerpts(session, resolved.facts, shown, page_chars, page_limit)
            if page_limit > 0
            else []
        )
        items.append(ResolvedItem(ref, resolved.label, resolved.facts, pages))
    return items


def fallback_label(ref: AskRef) -> str:
    """A label for an item that no longer resolves, as a turn served later may hold."""
    match ref:
        case AskKpiRef():
            return _TILE_WORDS[ref.name]
        case AskStageRef():
            return "Case stage"
        case AskProviderRef():
            return "Provider"
        case AskCallRef():
            return "Call"
        case AskSourceRef():
            return "Record"
        case _:
            return "Records"


def _resolve(
    session: Session, matter_id: int, ref: AskRef, renderable: dict[int, Fact]
) -> _Resolved:
    match ref:
        case AskFactsRef():
            return _facts(ref, renderable)
        case AskSourceRef():
            return _source(session, matter_id, ref, renderable)
        case AskProviderRef():
            return _provider(session, matter_id, ref, renderable)
        case AskCallRef():
            return _call(session, matter_id, ref, renderable)
        case AskKpiRef():
            return _kpi(ref, renderable)
        case AskStageRef():
            return _stage(session, matter_id, renderable)


def _facts(ref: AskFactsRef, renderable: dict[int, Fact]) -> _Resolved:
    ids = list(dict.fromkeys(ref.fact_ids))
    if any(i not in renderable for i in ids):
        raise ItemNotInMatter("a pointed-at fact is not in this matter")
    own = [renderable[i] for i in ids]
    kinds = {f.kind for f in own}
    candidates = [f for f in renderable.values() if f.kind in kinds]
    restated = [r for f in own for r in restatements_of(f, candidates)]
    facts = list({f.id: f for f in [*own, *restated]}.values())
    label = _fact_label(own[0])
    if len(own) > 1:
        label = f"{label} and {len(own) - 1} more"
    return _Resolved(label, facts[:MAX_ITEM_FACTS])


def _source(
    session: Session, matter_id: int, ref: AskSourceRef, renderable: dict[int, Fact]
) -> _Resolved:
    source = session.get(Source, ref.source_id)
    if source is None or source.matter_id != matter_id:
        raise ItemNotInMatter("a pointed-at record is not in this matter")
    facts = _most_significant(
        [f for f in renderable.values() if f.source_id == source.id]
    )
    return _Resolved(
        _dated(_SOURCE_WORDS[source.clio_type], source_date(source)),
        facts[:MAX_ITEM_FACTS],
    )


def _provider(
    session: Session, matter_id: int, ref: AskProviderRef, renderable: dict[int, Fact]
) -> _Resolved:
    facts = _most_significant(
        [f for f in renderable.values() if f.provider_contact_id == ref.contact_id]
    )
    name = contact_name(session, matter_id, ref.contact_id)
    if not facts and name is None:
        raise ItemNotInMatter("a pointed-at provider is not in this matter")
    label = f"Provider, {name}" if name else "Provider"
    return _Resolved(label, facts[:MAX_ITEM_FACTS])


def _call(
    session: Session, matter_id: int, ref: AskCallRef, renderable: dict[int, Fact]
) -> _Resolved:
    call = session.get(Call, ref.call_id)
    if call is None or call.matter_id != matter_id:
        raise ItemNotInMatter("a pointed-at call is not in this matter")
    notes = [
        f
        for f in renderable.values()
        if call.source_id is not None
        and f.source_id == call.source_id
        and f.kind is FactKind.CALL_NOTE
    ]
    return _Resolved(
        _dated("Call", call.started_at.date()),
        _most_significant(notes)[:MAX_ITEM_FACTS],
    )


def _stage(session: Session, matter_id: int, renderable: dict[int, Fact]) -> _Resolved:
    """The header's stage facts, then the dated events that moved the case (D51).

    The stage field says where the case is, not how it got there, so a question about
    the stage also carries the status changes and court events, latest first. The cap
    is the number of an item's rows the model is shown, so the significance ranking
    that picks those rows (`digest/chat.py`) drops none of them.
    """
    header = matter_stage(session, matter_id).facts
    stage = [renderable[r.id] for r in header if r.id in renderable]
    moves = sorted(
        (
            f
            for f in renderable.values()
            if f.kind in _MOVED_THE_CASE and f.event_date is not None
        ),
        key=lambda f: (-(f.event_date or date.min).toordinal(), -f.significance, f.id),
    )
    facts = list({f.id: f for f in [*stage, *moves]}.values())
    cap = min(get_settings().chat_item_facts, MAX_ITEM_FACTS)
    return _Resolved("Case stage", facts[:cap])


def _kpi(ref: AskKpiRef, renderable: dict[int, Fact]) -> _Resolved:
    by_kind: dict[FactKind, list[Fact]] = {kind: [] for kind in FactKind}
    for fact in renderable.values():
        by_kind[fact.kind].append(fact)
    tile = next(t for t in kpi_tiles(by_kind) if t.name == ref.name)
    ids = dict.fromkeys(r.id for value in tile.values for r in value.facts)
    facts = [renderable[i] for i in ids if i in renderable]
    return _Resolved(_TILE_WORDS[ref.name], facts[:MAX_ITEM_FACTS])


def _fact_label(fact: Fact) -> str:
    return _dated(_KIND_WORDS.get(fact.kind, "Record"), fact.event_date)


def _dated(word: str, on: date | None) -> str:
    return f"{word}, {on:%b} {on.day}, {on.year}" if on is not None else word


def _most_significant(facts: list[Fact]) -> list[Fact]:
    """Most significant first, so the cut to MAX_ITEM_FACTS keeps what matters."""
    return sorted(
        facts,
        key=lambda f: (-f.significance, -(f.event_date or date.min).toordinal(), f.id),
    )
