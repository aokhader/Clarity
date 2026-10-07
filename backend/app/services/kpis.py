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

_PER_LABELS: dict[str | None, str] = {
    "person": "Per person",
    "occurrence": "Per occurrence",
}
_LABEL_ORDER: list[str | None] = ["Per person", "Per occurrence", None]


@dataclass(frozen=True)
class _Statement:
    """Facts that state one figure, and the record they come from."""

    amounts: _Amounts
    facts: list[Fact]
    record: int | str  # a source id, or _BILL_SUM
    label: str | None = None  # what the figure is, when the tile mixes kinds


def _stated(amounts: _Amounts, fact: Fact, label: str | None = None) -> _Statement:
    return _Statement(amounts, [fact], fact.source_id, label)


def _records(group: list[_Statement]) -> set[int | str]:
    return {s.record for s in group}


def _grouped(statements: list[_Statement]) -> list[list[_Statement]]:
    """Statements of the same figure together, the figure the most records state first.

    Ties keep the order given, which is most significant first.
    """
    groups: dict[tuple[_Amounts, str | None], list[_Statement]] = {}
    for statement in statements:
        groups.setdefault((statement.amounts, statement.label), []).append(statement)
    return sorted(groups.values(), key=lambda group: -len(_records(group)))


def _value(group: list[_Statement]) -> KpiValueOut:
    amount, low, high = group[0].amounts
    return KpiValueOut(
        amount_cents=amount,
        low_cents=low,
        high_cents=high,
        label=group[0].label,
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
        # A one-ended value ("at least X") stays one-ended: it is not the point value X.
        if low is None and high is None:
            continue
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
    """Every stated limit, each labelled per person or per occurrence.

    A per-occurrence limit is not a per-person one, so each value carries its own label,
    per-person limits first, and the basis names the kind only when every value shares it.
    """
    statements = [
        _stated((payload.amount_cents, None, None), fact, _PER_LABELS.get(payload.per))
        for fact in _most_significant_first(facts)
        if (payload := PolicyLimitPayload.model_validate(fact.value_json)).amount_cents
        is not None
    ]
    groups = sorted(_grouped(statements), key=lambda g: _LABEL_ORDER.index(g[0].label))
    labels = {g[0].label for g in groups}
    return KpiOut(
        name="coverage",
        values=[_value(g) for g in groups],
        basis=labels.pop() if len(labels) == 1 else None,
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
    # A figure the bills confirm leads: the file states it and also adds up to it.
    groups = sorted(
        _grouped(statements),
        key=lambda g: not (_BILL_SUM in _records(g) and len(_records(g)) > 1),
    )
    bill_count = _plural(len(billed_facts), "bill")
    if not billed_facts:
        basis = None
    elif not stated_amounts:
        basis = f"Sum of {bill_count}"
    elif total not in stated_amounts:
        basis = f"Differs from the sum of {bill_count}"
    elif len(groups) == 1:
        basis = f"Matches the sum of {bill_count}"
    else:
        # Another figure disagrees, so the tile warns; the basis says which one the
        # bills confirm rather than that the tile "matches".
        basis = f"The first figure is the sum of {bill_count}"
    return KpiOut(
        name="medical_specials", values=[_value(g) for g in groups], basis=basis
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
