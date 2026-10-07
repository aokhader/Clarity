"""The four KPI tiles: case value, coverage, medical specials, and firm spend.

A tile lists every distinct value the file supports, each with its sources. No
value means "Not found in file"; two or more mean the sources disagree. Nothing is
estimated or guessed.

When sources disagree, the figure stated by the most records comes first, so one
misread line cannot become the headline over a figure the file states again and again.
"""

from dataclasses import dataclass

from app.models import Fact, FactKind
from app.schemas import (
    CaseValuePayload,
    ExpensePayload,
    KpiOut,
    KpiValueOut,
    MedicalSpecialsPayload,
    PolicyLimitPayload,
)
from app.services.bills import count_bills
from app.services.fact_views import fact_ref

# (amount, low, high) in cents. Facts with the same amounts agree and share a value.
_Amounts = tuple[int | None, int | None, int | None]

# The record key of the bill sum: however many bills add up to it, it is one figure.
_BILL_SUM = "bills"


@dataclass(frozen=True)
class _Statement:
    """Facts that state one figure, and the record they come from."""

    amounts: _Amounts
    facts: list[Fact]
    record: int | str  # a source id, or _BILL_SUM


def _stated(amounts: _Amounts, fact: Fact) -> _Statement:
    return _Statement(amounts, [fact], fact.source_id)


def _grouped(statements: list[_Statement]) -> list[list[_Statement]]:
    """Statements of the same figure together, the figure the most records state first.

    Ties keep the order given, which is most significant first.
    """
    groups: dict[_Amounts, list[_Statement]] = {}
    for statement in statements:
        groups.setdefault(statement.amounts, []).append(statement)
    return sorted(groups.values(), key=lambda group: -len({s.record for s in group}))


def _value(group: list[_Statement]) -> KpiValueOut:
    amount, low, high = group[0].amounts
    return KpiValueOut(
        amount_cents=amount,
        low_cents=low,
        high_cents=high,
        facts=[fact_ref(f) for s in group for f in s.facts],
    )


def _most_significant_first(facts: list[Fact]) -> list[Fact]:
    return sorted(facts, key=lambda f: f.significance, reverse=True)


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _case_value(facts: list[Fact]) -> KpiOut:
    statements: list[_Statement] = []
    for fact in _most_significant_first(facts):
        payload = CaseValuePayload.model_validate(fact.value_json)
        low, high = payload.low_cents, payload.high_cents
        if low is None and high is None:
            continue
        if low is None or high is None:
            # One figure written as either end is the same value as a range of one: the
            # tile shows both as that single figure.
            low = high = low if low is not None else high
        statements.append(_stated((None, low, high), fact))
    groups = _grouped(statements)
    # The basis line explains the figure the tile leads with.
    basis = None
    if groups:
        basis = next(
            (
                b
                for s in groups[0]
                if (b := CaseValuePayload.model_validate(s.facts[0].value_json).basis)
            ),
            None,
        )
    return KpiOut(name="case_value", values=[_value(g) for g in groups], basis=basis)


def _coverage(facts: list[Fact]) -> KpiOut:
    """Limits of one kind: per person when the file states any, else per occurrence.

    A per-occurrence limit is not a per-person limit, and the tile has one basis line,
    so it shows one kind. A limit whose kind is not stated shows only when no limit
    states one.
    """
    priced = [
        (fact, payload)
        for fact in _most_significant_first(facts)
        if (payload := PolicyLimitPayload.model_validate(fact.value_json)).amount_cents
        is not None
    ]
    stated_kinds = {payload.per for _, payload in priced}
    per = next((k for k in ("person", "occurrence") if k in stated_kinds), None)
    statements = [
        _stated((payload.amount_cents, None, None), fact)
        for fact, payload in priced
        if per is None or payload.per == per
    ]
    return KpiOut(
        name="coverage",
        values=[_value(g) for g in _grouped(statements)],
        basis=f"Per {per}" if per else None,
    )


def _medical_specials(specials: list[Fact], bills: list[Fact]) -> KpiOut:
    """The specials figure, checked against the bills with each provider counted once."""
    statements: list[_Statement] = []
    for fact in _most_significant_first(specials):
        amount = MedicalSpecialsPayload.model_validate(fact.value_json).amount_cents
        if amount is not None:
            statements.append(_stated((amount, None, None), fact))
    stated_amounts = {s.amounts[0] for s in statements}
    # Each provider's charges count once, however many records restate them.
    counted = count_bills(bills)
    billed_facts = [fact for c in counted for fact in c.facts]
    total = sum(c.total_cents for c in counted)
    if billed_facts:
        statements.append(_Statement((total, None, None), billed_facts, _BILL_SUM))
    bill_count = _plural(len(billed_facts), "bill")
    if not billed_facts:
        basis = None
    elif not stated_amounts:
        basis = f"Sum of {bill_count}"
    elif total in stated_amounts:
        basis = f"Matches the sum of {bill_count}"
    else:
        basis = f"Differs from the sum of {bill_count}"
    return KpiOut(
        name="medical_specials",
        values=[_value(g) for g in _grouped(statements)],
        basis=basis,
    )


def _firm_spend(expenses: list[Fact]) -> KpiOut:
    counted = [
        (ExpensePayload.model_validate(f.value_json).amount_cents, f) for f in expenses
    ]
    counted = [(amount, f) for amount, f in counted if amount is not None]
    if not counted:
        return KpiOut(name="firm_spend", values=[], basis=None)
    value = KpiValueOut(
        amount_cents=sum(amount for amount, _ in counted),
        facts=[fact_ref(f) for _, f in counted],
    )
    return KpiOut(
        name="firm_spend", values=[value], basis=_plural(len(counted), "expense")
    )


def kpi_tiles(by_kind: dict[FactKind, list[Fact]]) -> list[KpiOut]:
    return [
        _case_value(by_kind[FactKind.CASE_VALUE]),
        _coverage(by_kind[FactKind.POLICY_LIMIT]),
        _medical_specials(
            by_kind[FactKind.MEDICAL_SPECIALS], by_kind[FactKind.MEDICAL_BILL]
        ),
        _firm_spend(by_kind[FactKind.EXPENSE]),
    ]
