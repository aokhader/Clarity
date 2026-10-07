"""Re-read chosen pages and records with the current prompts, and only those.

Extraction skips a page or record it has read before, so a reworded prompt never reaches
existing facts on its own. This marks the chosen ones unread. The next digest reads
them again through `llm.py`, cached like any other call, replaces their facts, and
scores the new ones. Nothing else is read again.
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.digest.records import display_date, parse_date
from app.models import Fact, FactKind, LlmCall, Origin, Page, Source, SourceType

# Records the extractor reads whole; the matter stands for its custom fields.
REREADABLE_RECORDS = {SourceType.NOTE, SourceType.COMMUNICATION, SourceType.MATTER}


class NotRereadable(ValueError):
    """A named page, record or fact that extraction does not read."""


@dataclass
class Selection:
    pages: list[Page] = field(default_factory=list)
    records: list[Source] = field(default_factory=list)


@dataclass(frozen=True)
class Estimate:
    """At most this much: a unit whose answer is already cached costs nothing."""

    extraction_calls: int
    facts_held: int
    usd: Decimal | None  # None when no call has been recorded to price it by


def select_units(
    session: Session,
    matter_id: int,
    *,
    pages: Iterable[tuple[int, int]] = (),
    records: Iterable[int] = (),
    fact_ids: Iterable[int] = (),
    kinds: Iterable[str] = (),
) -> Selection:
    """Pages (document source id, page number) and records, named or behind facts."""
    page_keys = set(pages)
    record_ids = set(records)
    for fact in _facts(session, matter_id, list(fact_ids), list(kinds)):
        if fact.origin is not Origin.MODEL:
            raise NotRereadable(
                f"fact {fact.id} is built in code; a digest rebuilds it"
            )
        if fact.page_no is not None and fact.source.clio_type is SourceType.DOCUMENT:
            page_keys.add((fact.source_id, fact.page_no))
        else:
            record_ids.add(fact.source_id)
    return Selection(
        pages=[_page(session, matter_id, key) for key in sorted(page_keys)],
        records=[_record(session, matter_id, rid) for rid in sorted(record_ids)],
    )


def mark_unread(selection: Selection) -> None:
    for page in selection.pages:
        page.extracted_at = None
    for record in selection.records:
        # Notes and emails compare it with their text; the matter with its request.
        record.content_hash = None


def estimate(session: Session, selection: Selection) -> Estimate:
    """Upper bound from the average recorded cost of each kind of call."""
    held = _facts_held(session, selection)
    calls = len(selection.pages) + len(selection.records)
    page_cost = _average_cost(session, "extract_page")
    record_cost = _average_cost(session, "extract_record")
    fact_cost = _scoring_cost_per_fact(session)
    brief_cost = _average_cost(session, "brief")
    parts = [
        (len(selection.pages), page_cost),
        (len(selection.records), record_cost),
        (held, fact_cost),
        (1, brief_cost),
    ]
    if any(cost is None for count, cost in parts if count):
        return Estimate(calls, held, None)
    usd = sum((count * (cost or 0) for count, cost in parts), Decimal(0))
    return Estimate(calls, held, usd / 1_000_000)


def _facts(
    session: Session, matter_id: int, fact_ids: list[int], kinds: list[str]
) -> list[Fact]:
    facts: list[Fact] = []
    if fact_ids:
        found = session.scalars(
            select(Fact).where(Fact.matter_id == matter_id, Fact.id.in_(fact_ids))
        ).all()
        missing = set(fact_ids) - {f.id for f in found}
        if missing:
            raise NotRereadable(f"no facts {sorted(missing)} on matter {matter_id}")
        facts.extend(found)
    if kinds:
        facts.extend(
            session.scalars(
                select(Fact).where(
                    Fact.matter_id == matter_id,
                    Fact.kind.in_([FactKind(k) for k in kinds]),
                    Fact.origin == Origin.MODEL,
                )
            ).all()
        )
    return facts


def _page(session: Session, matter_id: int, key: tuple[int, int]) -> Page:
    source_id, page_no = key
    page = session.scalars(
        select(Page)
        .join(Source)
        .where(
            Source.matter_id == matter_id,
            Page.source_id == source_id,
            Page.page_no == page_no,
        )
    ).first()
    if page is None:
        raise NotRereadable(f"no page {page_no} of document source {source_id}")
    return page


def _record(session: Session, matter_id: int, source_id: int) -> Source:
    source = session.get(Source, source_id)
    if source is None or source.matter_id != matter_id:
        raise NotRereadable(f"no source {source_id} on matter {matter_id}")
    if source.clio_type not in REREADABLE_RECORDS:
        raise NotRereadable(
            f"source {source_id} is a {source.clio_type.value}, which code reads"
        )
    return source


def describe(session: Session, selection: Selection) -> list[str]:
    """One line per unit, by id and date only: titles and text are case data."""
    lines = []
    for page in selection.pages:
        held = _held(_page_facts(session, page))
        lines.append(f"page {page.page_no} of document source {page.source_id}: {held}")
    for record in selection.records:
        day = display_date(parse_date(record.raw_json.get("date")))
        dated = f", {day}" if day else ""
        held = _held(_record_facts(session, record))
        lines.append(f"{record.clio_type.value} source {record.id}{dated}: {held}")
    return lines


def _held(facts: list[Fact]) -> str:
    if not facts:
        return "no facts"
    kinds = Counter(f.kind.value for f in facts)
    listed = ", ".join(
        f"{kind} x{n}" if n > 1 else kind for kind, n in sorted(kinds.items())
    )
    noun = "fact" if len(facts) == 1 else "facts"
    return f"{len(facts)} {noun} ({listed})"


def _page_facts(session: Session, page: Page) -> list[Fact]:
    return list(
        session.scalars(
            select(Fact).where(
                Fact.source_id == page.source_id,
                Fact.page_no == page.page_no,
                Fact.origin == Origin.MODEL,
            )
        )
    )


def _record_facts(session: Session, record: Source) -> list[Fact]:
    return list(
        session.scalars(
            select(Fact).where(Fact.source_id == record.id, Fact.origin == Origin.MODEL)
        )
    )


def _facts_held(session: Session, selection: Selection) -> int:
    return sum(len(_page_facts(session, p)) for p in selection.pages) + sum(
        len(_record_facts(session, r)) for r in selection.records
    )


def _answered_calls(session: Session, purpose: str) -> list[LlmCall]:
    return list(
        session.scalars(
            select(LlmCall).where(
                LlmCall.purpose == purpose,
                LlmCall.cache_hit.is_(False),
                LlmCall.response_json.is_not(None),
            )
        )
    )


def _average_cost(session: Session, purpose: str) -> Decimal | None:
    """Micro-dollars per answered call."""
    calls = _answered_calls(session, purpose)
    if not calls:
        return None
    return Decimal(sum(c.cost_micro_usd for c in calls)) / len(calls)


def _scoring_cost_per_fact(session: Session) -> Decimal | None:
    calls = _answered_calls(session, "significance")
    scored = sum(len((c.response_json or {}).get("scores", [])) for c in calls)
    if not scored:
        return None
    return Decimal(sum(c.cost_micro_usd for c in calls)) / scored
