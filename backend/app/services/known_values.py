"""Amounts and dates the file holds, in the form the text matcher compares against.

A `KnownValue` is one figure or date, with the facts that state it and plain words for
what it is. `fact_values` reads every amount and date a fact carries, including a
second read that disagreed (`alt_values`) and the figures a call note lists, so a check
can recognise any of them.
"""

from dataclasses import dataclass
from datetime import date, datetime
from functools import partial
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
    # Withheld only: locks on an exact match, never on a rounded figure or a range. For
    # values of facts the link releases but does not display (a balance, a second read),
    # which a rounded figure about the provider's own bill would otherwise hit.
    exact_only: bool = False


def fact_values(
    fact: Fact, what: str, rank: int = 0, *, exact_only: bool = False
) -> list[KnownValue]:
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
    # A call note lists every figure its quote states.
    amounts |= {a for a in payload.get("amounts_cents") or [] if isinstance(a, int)}
    days = {fact.event_date} if fact.event_date else set()
    days |= {_day(read.get("on")) for read in reads} - {None}
    days |= {_day(payload.get("due_at"))} - {None}
    months: set[date] = set()
    for mentioned in payload.get("dates") or []:
        if not isinstance(mentioned, dict) or (on := _day(mentioned.get("on"))) is None:
            continue
        (months if mentioned.get("precision") == "month" else days).add(on)
    known = partial(KnownValue, what, facts=(fact,), rank=rank, exact_only=exact_only)
    return (
        [known(amount_cents=cents) for cents in sorted(amounts)]
        + [known(on=day) for day in sorted(d for d in days if d)]
        + [known(on=month, month_only=True) for month in sorted(months)]
    )


def _day(value: object) -> date | None:
    """A payload date or datetime (ISO text) as its calendar day."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None
