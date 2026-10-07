"""The four KPI tiles: case value, coverage, medical specials, and firm spend.

A tile lists every distinct value the file supports, each with its sources. No
value means "Not found in file"; two figures for the same thing mean the sources
disagree. Nothing is estimated or guessed.

When sources disagree, the figure stated by the most records comes first, so one
misread line cannot become the headline over a figure the file states again and again.
"""

from dataclasses import dataclass
from itertools import combinations

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

# (policy, per) of a limit; None where the file does not say.
_LimitKind = tuple[str | None, str | None]
_POLICY_NAMES: dict[str, str] = {
    "defendant_liability": "Defendant liability",
    "client_no_fault": "Client no-fault",
    "client_um_uim": "Client UM/UIM",
    "client_other": "Client's other policy",
}
_PER_WORDS = {"person": "per person", "occurrence": "per occurrence"}


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
    values = [_value(g) for g in groups]
    return KpiOut(
        name="case_value",
        values=values,
        basis=basis,
        sources_disagree=len(values) > 1,
    )


def _coverage(facts: list[Fact]) -> KpiOut:
    """Every stated limit, labelled by whose policy it is and per person or occurrence.

    The defendant's liability limit leads, then the client's own policies, then limits
    whose policy is not known. Different policies are separate entries, not a
    disagreement: two figures disagree only when they could be the same limit.
    """
    statements: list[_Statement] = []
    kind_of: dict[str | None, _LimitKind] = {}
    for fact in _most_significant_first(facts):
        payload = PolicyLimitPayload.model_validate(fact.value_json)
        if payload.amount_cents is None:
            continue
        label = _limit_label(payload.policy, payload.per)
        kind_of[label] = (payload.policy, payload.per)
        statements.append(_stated((payload.amount_cents, None, None), fact, label))
    groups = sorted(_grouped(statements), key=lambda g: _LABEL_ORDER.index(g[0].label))
    labels = {g[0].label for g in groups}
    limits = [(g[0].amounts[0], kind_of[g[0].label]) for g in groups]
    return KpiOut(
        name="coverage",
        values=[_value(g) for g in groups],
        basis=labels.pop() if len(labels) == 1 else None,
        sources_disagree=any(_conflict(a, b) for a, b in combinations(limits, 2)),
    )


def _limit_label(policy: str | None, per: str | None) -> str | None:
    per_words = _PER_WORDS.get(per or "")
    if policy is None:
        return per_words.capitalize() if per_words else None
    name = _POLICY_NAMES[policy]
    return f"{name}, {per_words}" if per_words else name


# Tile order: the defendant's policy, then the client's, then policy unknown; per
# person before per occurrence.
_LABEL_ORDER = [
    _limit_label(policy, per)
    for policy in [*_POLICY_NAMES, None]
    for per in ("person", "occurrence", None)
]


def _conflict(
    a: tuple[int | None, _LimitKind], b: tuple[int | None, _LimitKind]
) -> bool:
    """Two different figures that could be the same limit: the same per, and the same
    policy, where an unknown policy or per could be either."""
    (amount_a, (policy_a, per_a)), (amount_b, (policy_b, per_b)) = a, b
    return (
        amount_a != amount_b
        and _may_match(policy_a, policy_b)
        and _may_match(per_a, per_b)
    )


def _may_match(one: str | None, other: str | None) -> bool:
    return one == other or one is None or other is None


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
        name="medical_specials",
        values=[_value(g) for g in groups],
        basis=basis,
        sources_disagree=len(groups) > 1,
    )


def _firm_spend(expenses: list[Fact]) -> KpiOut:
    counted = [
        (ExpensePayload.model_validate(f.value_json).amount_cents, f) for f in expenses
    ]
    counted = [(amount, f) for amount, f in counted if amount is not None]
    if not counted:
        return KpiOut(name="firm_spend", values=[], basis=None, sources_disagree=False)
    value = KpiValueOut(
        amount_cents=sum(amount for amount, _ in counted),
        facts=[fact_ref(f) for _, f in counted],
    )
    return KpiOut(
        name="firm_spend",
        values=[value],
        basis=_plural(len(counted), "expense"),
        sources_disagree=False,
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
