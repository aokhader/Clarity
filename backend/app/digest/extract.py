"""Stage 3: model extraction over document pages, notes, communications, and custom fields.

One page or one record per call, so every fact keeps its page attribution. Inputs that
were already extracted with the same content are skipped; the model-call cache makes a
repeat run free even when they are not.
"""

import json
import logging
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.digest import llm
from app.digest.mapping import MatterMapping
from app.digest.pages import mark_extracted
from app.digest.payloads import model_payload
from app.digest.records import (
    QUOTE_LIMIT,
    is_processed,
    mark_processed,
    parse_date,
    record_text,
    replace_facts,
    sources_of,
)
from app.digest.verify import (
    SECOND_READ_KINDS,
    compare_reads,
    quote_in_text,
    resolve_provider,
    sane_date,
)
from app.models import Confidence, Fact, FactKind, Origin, Page, Source, SourceType

log = logging.getLogger(__name__)

_DIGITS = re.compile(r"\d")
# Structured records produce these kinds in code; the extractor never does.
CODE_ONLY_KINDS = {FactKind.CASE_STAGE, FactKind.TASK}
ExtractKind = Literal[tuple(k.value for k in FactKind if k not in CODE_ONLY_KINDS)]  # type: ignore[valid-type]
DocumentType = Literal[
    "medical_record",
    "bill",
    "lien_notice",
    "insurance",
    "police_report",
    "correspondence",
    "legal_filing",
    "intake",
    "other",
]


class ExtractedFact(BaseModel):
    kind: ExtractKind
    title: str
    event_date: str | None = None
    amount: float | None = None
    provider_contact_id: int | None = None
    provider_name_as_written: str | None = None
    quote: str
    mentions_strategy: bool = False
    detail: dict[str, Any] = {}


class Extraction(BaseModel):
    document_type: DocumentType
    facts: list[ExtractedFact]


class SecondRead(BaseModel):
    amount: float | None = None
    event_date: str | None = None


@dataclass
class Unit:
    """One extraction input: a page or a record."""

    source: Source
    request: llm.ModelRequest
    text: str | None  # None for scans: there is no text to check quotes against
    page: Page | None = None
    image: bytes | None = None


def extract_all(
    session: Session, matter_id: int, mapping: MatterMapping
) -> Counter[str]:
    counts: Counter[str] = Counter()
    providers = mapping.providers()
    units = _record_units(session, matter_id, mapping, providers, counts)
    units += _page_units(session, matter_id, providers)
    batch_size = get_settings().extract_batch_size
    for start in range(0, len(units), batch_size):
        chunk = units[start : start + batch_size]
        results = llm.run_batch(session, [u.request for u in chunk])
        second_reads: list[tuple[Fact, Unit, float | None]] = []
        for unit, result in zip(chunk, results, strict=True):
            if not isinstance(result, Extraction):
                counts["failed"] += 1
                continue
            facts = _to_facts(unit, result, providers, counts, second_reads)
            page_no = unit.page.page_no if unit.page else None
            replace_facts(session, unit.source, facts, Origin.MODEL, page_no=page_no)
            if unit.page is not None:
                mark_extracted(unit.page)
            elif unit.source.clio_type is SourceType.MATTER:
                unit.source.content_hash = unit.request.cache_key
            else:
                mark_processed(unit.source)
            counts["facts"] += len(facts)
        _second_reads(session, matter_id, second_reads, counts)
        session.commit()
        log.info(
            "Extraction progress: %d of %d inputs",
            min(start + batch_size, len(units)),
            len(units),
        )
    log.info("Extraction: %s", dict(counts))
    return counts


def _record_units(
    session: Session,
    matter_id: int,
    mapping: MatterMapping,
    providers: dict[int, str],
    counts: Counter[str],
) -> list[Unit]:
    units: list[Unit] = []
    candidates = sources_of(session, matter_id, SourceType.NOTE) + sources_of(
        session, matter_id, SourceType.COMMUNICATION
    )
    for source in candidates:
        if is_processed(source):
            counts["unchanged"] += 1
            continue
        text = record_text(source)
        units.append(_record_unit(source, text, providers, matter_id))
    # The custom fields code cannot read go in as one record, sourced to the matter.
    # The mapping decides its content, so its marker is the request's cache key. An
    # unchanged one is not applied again, so dedup's removals among its facts stand.
    if mapping.matter is not None and mapping.extraction_text:
        unit = _record_unit(
            mapping.matter, mapping.extraction_text, providers, matter_id
        )
        if mapping.matter.content_hash == unit.request.cache_key:
            counts["unchanged"] += 1
        else:
            units.append(unit)
    return units


def _record_unit(
    source: Source, text: str, providers: dict[int, str], matter_id: int
) -> Unit:
    return Unit(
        source=source,
        text=text,
        request=llm.ModelRequest(
            purpose="extract_record",
            role="extract",
            prompt=llm.load_prompt("extract_record"),
            user_text=_with_providers(text, providers),
            output=Extraction,
            matter_id=matter_id,
            source_id=source.id,
        ),
    )


def _page_units(
    session: Session, matter_id: int, providers: dict[int, str]
) -> list[Unit]:
    pages = session.scalars(
        select(Page)
        .join(Source)
        .where(Source.matter_id == matter_id, Page.extracted_at.is_(None))
        .order_by(Page.source_id, Page.page_no)
    ).all()
    totals = dict(
        session.execute(
            select(Page.source_id, func.max(Page.page_no))
            .join(Source)
            .where(Source.matter_id == matter_id)
            .group_by(Page.source_id)
        )
        .tuples()
        .all()
    )
    data_dir = get_settings().data_dir
    units: list[Unit] = []
    for page in pages:
        source = page.source
        name = str(source.raw_json.get("name") or f"document {source.clio_id}")
        header = f"Document: {name}\nPage {page.page_no} of {max(totals.get(source.id, 1), page.page_no)}"
        image: bytes | None = None
        if page.has_text_layer and page.text:
            body = f"{header}\n\nPage text:\n{page.text}"
        elif page.image_path and (data_dir / page.image_path).exists():
            image = (data_dir / page.image_path).read_bytes()
            body = f"{header}\n\nThe page is a scanned image, attached."
        else:
            continue
        units.append(
            Unit(
                source=source,
                page=page,
                image=image,
                text=page.text if page.has_text_layer else None,
                request=llm.ModelRequest(
                    purpose="extract_page",
                    role="extract",
                    prompt=llm.load_prompt("extract_page"),
                    user_text=_with_providers(body, providers),
                    images=[image] if image else [],
                    output=Extraction,
                    matter_id=matter_id,
                    source_id=source.id,
                    page_no=page.page_no,
                ),
            )
        )
    return units


def _with_providers(text: str, providers: dict[int, str]) -> str:
    known = [{"contact_id": cid, "name": name} for cid, name in providers.items()]
    return f"Known providers: {json.dumps(known)}\n\n{text}"


def _to_facts(
    unit: Unit,
    extraction: Extraction,
    providers: dict[int, str],
    counts: Counter[str],
    second_reads: list[tuple[Fact, Unit, float | None]],
) -> list[Fact]:
    facts: list[Fact] = []
    for item in extraction.facts:
        kind = FactKind(item.kind)
        quote = item.quote.strip()[:QUOTE_LIMIT]
        if unit.text is not None and not quote_in_text(quote, unit.text):
            counts["dropped_quote"] += 1
            continue
        try:
            payload = model_payload(kind, item.amount, item.detail, item.title)
            if kind is FactKind.STATUS_CHANGE and not payload.get("to_stage"):
                # D41: a stage move names its stage. Without one the label is the
                # model's free text, often a court event, so it is kept as other.
                kind = FactKind.OTHER
                label = item.detail.get("label") or item.title
                payload = model_payload(kind, None, {"description": label})
                counts["status_change_without_stage"] += 1
        except ValidationError:
            counts["dropped_payload"] += 1
            continue
        provider_id = (
            item.provider_contact_id if item.provider_contact_id in providers else None
        )
        provider_id = provider_id or resolve_provider(
            item.provider_name_as_written, providers
        )
        fact = Fact(
            kind=kind,
            title=item.title.strip()[:120] or kind.value,
            quote=quote,
            event_date=sane_date(kind, parse_date(item.event_date)),
            value_json=payload,
            page_no=unit.page.page_no if unit.page else None,
            provider_contact_id=provider_id,
            mentions_strategy=item.mentions_strategy,
            # A scan has no text to match the quote against, so it starts lower.
            confidence=Confidence.HIGH if unit.text is not None else Confidence.MEDIUM,
            verified=unit.text is not None,
            significance=0,
        )
        if (
            unit.text is None
            and kind in SECOND_READ_KINDS
            and (item.amount is not None or fact.event_date)
        ):
            second_reads.append((fact, unit, item.amount))
        facts.append(fact)
    return facts


def _second_read_question(fact: Fact) -> str:
    """Name the item without its values, so the second read cannot copy the first.

    The quote and title of a scan fact usually carry the amount and date the first
    read produced; digits are masked so the model has to read them off the page again.
    """
    label = _DIGITS.sub("#", fact.title)
    return (
        f"Item to check: a {fact.kind.value.replace('_', ' ')}, described as: {label}"
    )


def _second_reads(
    session: Session,
    matter_id: int,
    pending: list[tuple[Fact, Unit, float | None]],
    counts: Counter[str],
) -> None:
    """Re-ask for money and dates on scans; agreement verifies, disagreement flags."""
    if not pending:
        return
    requests = [
        llm.ModelRequest(
            purpose="second_read",
            role="extract",
            prompt=llm.load_prompt("second_read"),
            user_text=_second_read_question(fact),
            images=[unit.image] if unit.image else [],
            output=SecondRead,
            matter_id=matter_id,
            source_id=unit.source.id,
            page_no=fact.page_no,
        )
        for fact, unit, _amount in pending
    ]
    results = llm.run_batch(session, requests)
    for (fact, _unit, first_amount), result in zip(pending, results, strict=True):
        if not isinstance(result, SecondRead):
            counts["second_read_failed"] += 1
            continue
        outcome = compare_reads(
            first_amount, fact.event_date, result.amount, parse_date(result.event_date)
        )
        fact.confidence = outcome.confidence
        fact.verified = outcome.verified
        if outcome.alt_values:
            fact.value_json = {**fact.value_json, "alt_values": outcome.alt_values}
            counts["second_read_disagreed"] += 1
        else:
            counts["second_read_agreed"] += 1
