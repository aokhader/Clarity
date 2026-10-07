"""Amounts and dates the file holds, in the form the text matcher compares against.

A `KnownValue` is one figure or date, with the facts that state it and plain words for
what it is. `fact_values` reads every amount and date a fact carries, including a
second read that disagreed (`alt_values`), so a check can recognise any of them.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from app.models import Fact

# Payload keys that hold money, in integer cents (PAYLOAD_BY_KIND in schemas.py).
_AMOUNT_KEYS = ("amount_cents", "balance_cents", "low_cents", "high_cents")


@dataclass(frozen=True)
class KnownValue:
    """An amount or a date the file holds, what it is, and the facts that state it."""

    what: str  # shown: "the bills total on this link"; withheld: the rule's reason
    amount_cents: int | None = None
    on: date | None = None
    month_only: bool = False  # `on` stands for its whole month
    facts: tuple[Fact, ...] = ()
    # Words that name the value's subject. A sentence that uses them and states another
    # value differs from this one. A value with no cues is never offered as the file's.
    cues: tuple[str, ...] = ()
    # Among withheld values that match, the reason of the lowest rank is given.
    rank: int = 0


def fact_values(fact: Fact, what: str, rank: int = 0) -> list[KnownValue]:
    """Every amount and date the fact carries, each stated by this fact."""
    payload: dict[str, Any] = fact.value_json or {}
    reads = [
        payload,
        *(a for a in payload.get("alt_values") or [] if isinstance(a, dict)),
    ]
    amounts = {
        read[key]
        for read in reads
        for key in _AMOUNT_KEYS
        if isinstance(read.get(key), int)
    }
    dates = {fact.event_date} if fact.event_date else set()
    dates |= {_day(read.get("on")) for read in reads} - {None}
    dates |= {_day(payload.get("due_at"))} - {None}
    return [
        KnownValue(what=what, amount_cents=cents, facts=(fact,), rank=rank)
        for cents in sorted(amounts)
    ] + [
        KnownValue(what=what, on=day, facts=(fact,), rank=rank)
        for day in sorted(d for d in dates if d is not None)
    ]


def _day(value: object) -> date | None:
    """A payload date or datetime (ISO text) as its calendar day."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None
