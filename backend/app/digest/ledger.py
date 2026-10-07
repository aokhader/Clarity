"""The firm's ledger: non-time activities, classified by one cached model call as a
firm cost or the client's medical charge, become `expense` or `medical_bill` facts with
the exact amount from Clio."""

import json
from collections import Counter
from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.digest import llm
from app.digest.payloads import build_payload
from app.digest.records import (
    QUOTE_LIMIT,
    display_date,
    name_of,
    parse_date,
    replace_facts,
    sources_of,
)
from app.digest.verify import resolve_provider
from app.models import (
    Confidence,
    Fact,
    FactKind,
    Origin,
    Source,
    SourceType,
)

TIME_ACTIVITY_TYPES = {"TimeEntry"}


class LedgerEntry(BaseModel):
    activity_id: int
    is_medical_charge: bool
    provider_contact_id: int | None = None
    provider_name_as_written: str | None = None


class LedgerMapping(BaseModel):
    activities: list[LedgerEntry]


def ledger_facts(
    session: Session, matter_id: int, providers: dict[int, str]
) -> Counter[str] | None:
    """Classify non-time activities into ledger facts; None when the call failed.

    On a failure nothing is replaced: a medical charge guessed to be a firm cost would
    move money from one KPI total to another.
    """
    counts: Counter[str] = Counter()
    activities = [
        a
        for a in sources_of(session, matter_id, SourceType.ACTIVITY)
        if a.raw_json.get("type") not in TIME_ACTIVITY_TYPES
    ]
    if not activities:
        return counts
    entries = [
        {
            "activity_id": a.id,
            "type": a.raw_json.get("type"),
            "date": a.raw_json.get("date"),
            "amount": str(activity_amount(a.raw_json)),
            "category": name_of(a.raw_json.get("expense_category")),
            "vendor": name_of(a.raw_json.get("vendor")),
            "note": str(a.raw_json.get("note") or "")[:500],
        }
        for a in activities
    ]
    known = [{"contact_id": cid, "name": name} for cid, name in providers.items()]
    result = llm.call(
        session,
        llm.ModelRequest(
            purpose="classify_activities",
            role="merge",
            prompt=llm.load_prompt("classify_activities"),
            user_text=json.dumps(
                {"known_providers": known, "entries": entries}, indent=1
            ),
            output=LedgerMapping,
            matter_id=matter_id,
        ),
    )
    if not isinstance(result, LedgerMapping):
        return None
    decisions = {e.activity_id: e for e in result.activities}
    for activity in activities:
        fact = ledger_fact(activity, decisions.get(activity.id), providers)
        replace_facts(session, activity, [fact], Origin.CODE)
        counts[fact.kind.value] += 1
    return counts


def activity_amount(raw: dict[str, Any]) -> Decimal:
    """`total` covers draft, billable, and billed amounts; non-billable is separate."""
    return Decimal(str(raw.get("total") or 0)) + Decimal(
        str(raw.get("non_billable_total") or 0)
    )


def ledger_fact(
    activity: Source, decision: LedgerEntry | None, providers: dict[int, str]
) -> Fact:
    raw = activity.raw_json
    category = name_of(raw.get("expense_category"))
    note = str(raw.get("note") or "")
    is_medical = bool(decision and decision.is_medical_charge)
    # Never the entry's own text as a title: firms type anything there, and a provider
    # reads this title as the name of its bill. The text stays as the quote.
    if is_medical:
        day = display_date(parse_date(raw.get("date")))
        label = (
            f"Charges on the firm's ledger, {day}"
            if day
            else "Charges on the firm's ledger"
        )
    else:
        label = category or "Firm expense"
    kind = FactKind.MEDICAL_BILL if is_medical else FactKind.EXPENSE
    provider_id = None
    if is_medical and decision:
        if decision.provider_contact_id in providers:
            provider_id = decision.provider_contact_id
        provider_id = provider_id or resolve_provider(
            decision.provider_name_as_written, providers
        )
    detail = (
        {}
        if is_medical
        else {"category": category, "vendor": name_of(raw.get("vendor"))}
    )
    return Fact(
        kind=kind,
        title=label[:120],
        quote=(note or category or label)[:QUOTE_LIMIT],
        event_date=parse_date(raw.get("date")),
        value_json=build_payload(kind, activity_amount(raw), detail),
        provider_contact_id=provider_id,
        # The amount is exact; only the medical-or-firm split came from a model.
        confidence=Confidence.HIGH if decision else Confidence.MEDIUM,
        verified=decision is not None,
        significance=0,
        mentions_strategy=False,
    )
