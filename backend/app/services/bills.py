"""One bill total per provider, however many records restate the same charges.

A provider's charges reach the fact store through up to three kinds of record: the
itemized bills in the provider's own documents, the firm's ledger in Clio, and notes or
emails that state a total. Each is a record of the same charges, so adding them together
counts a charge once per record. For each provider, only the most complete record is
counted; the others corroborate it.
"""

from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum

from app.models import Fact, FactKind, Origin, SourceType
from app.schemas import BillPayload

# Itemized bills still account for a stated total when they fall short of it by rounding.
ROUNDING_CENTS = 100


class BillRecord(StrEnum):
    ITEMIZED = "itemized"  # bills read from the provider's documents, each with a page
    LEDGER = "ledger"  # entries in the firm's Clio ledger
    STATED = "stated"  # totals stated in notes, emails, or matter fields


@dataclass(frozen=True)
class CountedBills:
    """The record counted for one provider, and the bills that make up its total."""

    provider_contact_id: int | None
    record: BillRecord
    total_cents: int
    facts: list[Fact]


def amount_cents(fact: Fact) -> int | None:
    return BillPayload.model_validate(fact.value_json).amount_cents


def record_of(fact: Fact) -> BillRecord:
    if fact.origin is Origin.CODE:
        return BillRecord.LEDGER
    if fact.source.clio_type is SourceType.DOCUMENT:
        return BillRecord.ITEMIZED
    return BillRecord.STATED


def _priced(record: BillRecord, facts: list[Fact]) -> list[Fact]:
    """The bills of one record that carry an amount, each charge once."""
    priced = [f for f in facts if amount_cents(f) is not None]
    if record is not BillRecord.STATED:
        return priced
    # Notes and emails repeat a total each time they mention it; the same amount is one bill.
    first_by_amount: dict[int | None, Fact] = {}
    for fact in priced:
        first_by_amount.setdefault(amount_cents(fact), fact)
    return list(first_by_amount.values())


def _total(facts: list[Fact]) -> int:
    return sum(amount_cents(f) or 0 for f in facts)


def count_provider_bills(
    provider_contact_id: int | None, bills: list[Fact]
) -> CountedBills | None:
    """Pick the record to count for one provider's bills.

    The most complete record wins. Itemized bills win whenever they account for that
    total, because each one cites a page a reader can open; otherwise the ledger, then a
    stated total. Returns None when no bill carries an amount.
    """
    by_record: dict[BillRecord, list[Fact]] = defaultdict(list)
    for fact in bills:
        by_record[record_of(fact)].append(fact)
    priced = {record: _priced(record, facts) for record, facts in by_record.items()}
    totals = {record: _total(facts) for record, facts in priced.items() if facts}
    if not totals:
        return None
    most = max(totals.values())
    for record in (BillRecord.ITEMIZED, BillRecord.LEDGER, BillRecord.STATED):
        tolerance = ROUNDING_CENTS if record is BillRecord.ITEMIZED else 0
        if record in totals and totals[record] + tolerance >= most:
            return CountedBills(
                provider_contact_id, record, totals[record], priced[record]
            )
    raise AssertionError("the largest record total always matches a record")


def count_bills(bills: list[Fact]) -> list[CountedBills]:
    """The counted record for every provider among these bills, unattributed bills as one group."""
    by_provider: dict[int | None, list[Fact]] = defaultdict(list)
    for fact in bills:
        if fact.kind is FactKind.MEDICAL_BILL:
            by_provider[fact.provider_contact_id].append(fact)
    unattributed = by_provider.pop(None, [])
    counted = [
        c
        for pid, facts in by_provider.items()
        if (c := count_provider_bills(pid, facts)) is not None
    ]
    # A note that states a provider's total without naming the provider restates that bill.
    provider_totals = {c.total_cents for c in counted}
    rest = [
        f
        for f in unattributed
        if record_of(f) is not BillRecord.STATED
        or amount_cents(f) not in provider_totals
    ]
    if (extra := count_provider_bills(None, rest)) is not None:
        counted.append(extra)
    return counted


def billed_total_cents(bills: list[Fact]) -> int:
    """The matter's billed total: each provider's counted record, added across providers."""
    return sum(c.total_cents for c in count_bills(bills))
