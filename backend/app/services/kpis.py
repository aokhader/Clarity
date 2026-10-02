"""The four KPI tiles: case value, coverage, medical specials, and firm spend.

A tile lists every distinct value the file supports, each with its sources. No
value means "Not found in file"; two or more mean the sources disagree. Nothing is
estimated or guessed.
"""

from app.models import Fact, FactKind
from app.schemas import (
    BillPayload,
    CaseValuePayload,
    ExpensePayload,
    KpiOut,
    KpiValueOut,
    MedicalSpecialsPayload,
    PolicyLimitPayload,
)
from app.services.fact_views import fact_ref

# (amount, low, high) in cents. Facts with the same amounts agree and share a value.
_Amounts = tuple[int | None, int | None, int | None]


def _values(entries: list[tuple[_Amounts, list[Fact]]]) -> list[KpiValueOut]:
    groups: dict[_Amounts, list[Fact]] = {}
    for amounts, facts in entries:
        groups.setdefault(amounts, []).extend(facts)
    return [
        KpiValueOut(
            amount_cents=amount,
            low_cents=low,
            high_cents=high,
            facts=[fact_ref(f) for f in facts],
        )
        for (amount, low, high), facts in groups.items()
    ]


def _most_significant_first(facts: list[Fact]) -> list[Fact]:
    return sorted(facts, key=lambda f: f.significance, reverse=True)


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _case_value(facts: list[Fact]) -> KpiOut:
    entries: list[tuple[_Amounts, list[Fact]]] = []
    basis = None
    for fact in _most_significant_first(facts):
        payload = CaseValuePayload.model_validate(fact.value_json)
        if payload.low_cents is None and payload.high_cents is None:
            continue
        entries.append(((None, payload.low_cents, payload.high_cents), [fact]))
        basis = basis or payload.basis
    return KpiOut(name="case_value", values=_values(entries), basis=basis)


def _coverage(facts: list[Fact]) -> KpiOut:
    entries: list[tuple[_Amounts, list[Fact]]] = []
    per = None
    for fact in _most_significant_first(facts):
        payload = PolicyLimitPayload.model_validate(fact.value_json)
        if payload.amount_cents is None:
            continue
        entries.append(((payload.amount_cents, None, None), [fact]))
        per = per or payload.per
    return KpiOut(
        name="coverage", values=_values(entries), basis=f"Per {per}" if per else None
    )


def _medical_specials(specials: list[Fact], bills: list[Fact]) -> KpiOut:
    """The specials figure, checked against the sum of the extracted bills."""
    entries: list[tuple[_Amounts, list[Fact]]] = []
    for fact in _most_significant_first(specials):
        amount = MedicalSpecialsPayload.model_validate(fact.value_json).amount_cents
        if amount is not None:
            entries.append(((amount, None, None), [fact]))
    billed = [(BillPayload.model_validate(f.value_json).amount_cents, f) for f in bills]
    billed_facts = [f for amount, f in billed if amount is not None]
    if billed_facts:
        total = sum(amount for amount, _ in billed if amount is not None)
        entries.append(((total, None, None), billed_facts))
    values = _values(entries)
    bill_count = _plural(len(billed_facts), "bill")
    if not billed_facts:
        basis = None
    elif len(entries) == 1:
        basis = f"Sum of {bill_count}"
    elif len(values) == 1:
        basis = f"Matches the sum of {bill_count}"
    else:
        basis = f"Differs from the sum of {bill_count}"
    return KpiOut(name="medical_specials", values=values, basis=basis)


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
