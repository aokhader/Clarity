"""Merge step 4: the brief, written by the merge model from stored facts only.

Code prepares everything the model might otherwise compute or convert: totals with the
ids of the facts they add up, money in dollars, dates written the way the app writes
them, and each fact's source by name. The model copies; it does not add or convert.
Every sentence, and the headline, must cite fact ids that exist.
"""

import json
import re
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.digest import llm
from app.digest.records import display_date, parse_date
from app.models import Digest, DigestKind, Fact, FactKind, SourceType
from app.schemas import BriefContent
from app.services.bills import count_bills

BRIEF_FACT_LIMIT = 40
# Figures the KPI tiles show; their facts are always in the brief's view.
FIGURE_KINDS = {FactKind.CASE_VALUE, FactKind.MEDICAL_SPECIALS, FactKind.POLICY_LIMIT}
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}")
Stage = Literal[
    "intake",
    "treating",
    "treatment_complete",
    "demand",
    "negotiation",
    "litigation",
    "settled",
    "closed",
]


class BriefSentence(BaseModel):
    text: str
    fact_ids: list[int]


class Brief(BaseModel):
    headline: str
    headline_fact_ids: list[int]
    stage: Stage
    stage_fact_ids: list[int]
    sentences: list[BriefSentence]
    open_questions: list[str] = []


def write_brief(session: Session, matter_id: int) -> bool:
    payload = brief_payload(session, matter_id)
    if not payload["facts"]:
        return False
    request = llm.ModelRequest(
        purpose="brief",
        role="merge",
        prompt=llm.load_prompt("brief"),
        user_text=json.dumps(payload, indent=1),
        output=Brief,
        matter_id=matter_id,
    )
    # The cache key covers the model, the prompt version and the input, so a new prompt
    # writes the brief again even when the facts have not changed.
    input_hash = request.cache_key
    existing = session.scalars(
        select(Digest).where(
            Digest.matter_id == matter_id, Digest.kind == DigestKind.BRIEF
        )
    ).first()
    if existing is not None and existing.input_hash == input_hash:
        return False
    result = llm.call(session, request)
    if not isinstance(result, Brief):
        return False
    cited = _cite_only_known(result, _citable_ids(payload))
    content = BriefContent.model_validate(cited.model_dump()).model_dump(mode="json")
    # Stored beside the contract's fields; backend reads it once BriefContent has it (B4).
    content["headline_fact_ids"] = cited.headline_fact_ids
    if existing is None:
        existing = Digest(
            matter_id=matter_id,
            kind=DigestKind.BRIEF,
            content_json=content,
            input_hash=input_hash,
            model=request.model,
        )
        session.add(existing)
    existing.content_json = content
    existing.input_hash = input_hash
    existing.model = request.model
    return True


def brief_payload(session: Session, matter_id: int) -> dict[str, Any]:
    """What the brief model is given: fact rows, computed totals, and open tasks."""
    facts = list(
        session.scalars(
            select(Fact).where(Fact.matter_id == matter_id).order_by(Fact.id)
        )
    )
    top = sorted(facts, key=lambda f: (-f.significance, f.id))[:BRIEF_FACT_LIMIT]
    stage_facts = [
        f for f in facts if f.kind in (FactKind.CASE_STAGE, FactKind.STATUS_CHANGE)
    ]
    open_tasks = [
        f
        for f in facts
        if f.kind is FactKind.TASK and f.value_json.get("status") != "complete"
    ]
    # The firm's own fields and the KPI figures are always in view, so the brief neither
    # misses them nor asks for them as open questions.
    figures = [
        f
        for f in facts
        if f.source.clio_type is SourceType.MATTER or f.kind in FIGURE_KINDS
    ]
    included = {f.id: f for f in top + stage_facts + open_tasks + figures}
    return {
        "facts": [_row(f) for f in included.values()],
        "key_figures": key_figures(facts),
        "open_task_ids": [f.id for f in open_tasks],
    }


def key_figures(facts: list[Fact]) -> dict[str, Any]:
    """Totals computed in code, each with the ids of the facts it adds up.

    A total with nothing behind it is left out rather than stated as zero.
    """
    figures: dict[str, Any] = {}
    # Each provider's charges count once, however many records restate them.
    counted = count_bills(facts)
    bills = sorted(f.id for c in counted for f in c.facts)
    if bills:
        figures["medical_bills_total"] = {
            "amount": dollars(sum(c.total_cents for c in counted)),
            "fact_ids": bills,
        }
    expenses = [
        f
        for f in facts
        if f.kind is FactKind.EXPENSE and (f.value_json or {}).get("amount_cents")
    ]
    if expenses:
        figures["firm_spend_total"] = {
            "amount": dollars(sum(f.value_json["amount_cents"] for f in expenses)),
            "fact_ids": [f.id for f in expenses],
        }
    return figures


def dollars(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    return f"{sign}${Decimal(abs(cents)) / 100:,.2f}"


def _row(fact: Fact) -> dict[str, Any]:
    return {
        "fact_id": fact.id,
        "kind": fact.kind.value,
        "title": fact.title,
        "date": display_date(fact.event_date),
        "source": _source_label(fact),
        "significance": fact.significance,
        "confidence": fact.confidence.value,
        "value": _display_value(fact.value_json or {}),
        "quote": (fact.quote or "")[:200],
    }


def _display_value(value: dict[str, Any]) -> dict[str, Any]:
    shown: dict[str, Any] = {}
    for key, item in value.items():
        if item is None or key in ("corroborating_source_ids", "alt_values"):
            continue
        if key.endswith("_cents") and isinstance(item, int):
            shown[key.removesuffix("_cents")] = dollars(item)
        elif isinstance(item, str) and _ISO_DATE.match(item):
            shown[key] = display_date(parse_date(item)) or item
        else:
            shown[key] = item
    return shown


def _source_label(fact: Fact) -> str:
    """The source by name and date, so facts from two records stay apart."""
    source = fact.source
    raw = source.raw_json or {}
    match source.clio_type:
        case SourceType.DOCUMENT:
            name = str(raw.get("name") or raw.get("filename") or "Document")
            return f"{name}, page {fact.page_no}" if fact.page_no else name
        case SourceType.NOTE | SourceType.COMMUNICATION:
            subject = str(raw.get("subject") or source.clio_type.value.capitalize())
            return _dated(subject, raw.get("date"))
        case SourceType.CALENDAR_ENTRY:
            return _dated(
                str(raw.get("summary") or "Calendar entry"), raw.get("start_at")
            )
        case SourceType.TASK:
            return f"Task: {raw.get('name') or 'untitled'}"
        case SourceType.ACTIVITY:
            # Never the entry's own text, which firms fill with anything.
            return _dated("Firm ledger entry", raw.get("date"))
        case SourceType.MATTER:
            return "The matter's fields in Clio"
        case _:
            return source.clio_type.value.replace("_", " ").capitalize()


def _dated(label: str, value: Any) -> str:
    day = display_date(parse_date(value)) if value else None
    return f"{label}, {day}" if day else label


def _citable_ids(payload: dict[str, Any]) -> set[int]:
    ids = {row["fact_id"] for row in payload["facts"]}
    for figure in payload["key_figures"].values():
        ids.update(figure["fact_ids"])
    return ids


def _cite_only_known(brief: Brief, known_ids: set[int]) -> Brief:
    """Drop any sentence that cites no real fact; a citation is the sentence's license.

    The headline stays even when none of its citations is real; it then cites nothing.
    """
    sentences = []
    for sentence in brief.sentences:
        ids = [i for i in sentence.fact_ids if i in known_ids]
        if ids:
            sentences.append(BriefSentence(text=sentence.text, fact_ids=ids))
    return brief.model_copy(
        update={
            "sentences": sentences,
            "headline_fact_ids": [i for i in brief.headline_fact_ids if i in known_ids],
            "stage_fact_ids": [i for i in brief.stage_fact_ids if i in known_ids],
        }
    )
