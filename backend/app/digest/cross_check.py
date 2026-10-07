"""Merge step 3: put the firm's own figures beside what the rest of the file says.

A disagreement is stored as `alt_values` on the firm's fact, so the source drawer shows
both numbers instead of silently picking one. Code compares; no model is involved.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Fact, FactKind, Source, SourceType
from app.services.bills import billed_total_cents


def cross_check(session: Session, matter_id: int) -> int:
    """Run every cross-check and return how many firm figures the file disagrees with."""
    facts = list(
        session.scalars(
            select(Fact).where(Fact.matter_id == matter_id).order_by(Fact.id)
        )
    )
    matter_sources = set(
        session.scalars(
            select(Source.id).where(
                Source.matter_id == matter_id, Source.clio_type == SourceType.MATTER
            )
        )
    )
    disagreements = _check_specials(facts) + _check_policy_limits(facts, matter_sources)
    session.flush()
    return disagreements


def _check_specials(facts: list[Fact]) -> int:
    """The billed total beside the firm's specials figure.

    The billed total counts each provider's charges once (`services/bills.py`): a ledger
    entry, a note, and the itemized bill for the same charges are one bill, not three.
    """
    bills = [f for f in facts if f.kind is FactKind.MEDICAL_BILL]
    total = billed_total_cents(bills)
    disagreements = 0
    for specials in (f for f in facts if f.kind is FactKind.MEDICAL_SPECIALS):
        value = dict(specials.value_json or {})
        stated = value.get("amount_cents")
        if bills and stated is not None and stated != total:
            value["alt_values"] = [{"amount_cents": total}]
            disagreements += 1
        else:
            value["alt_values"] = []
        specials.value_json = value
    return disagreements


def _check_policy_limits(facts: list[Fact], matter_sources: set[int]) -> int:
    """The limits the rest of the file states beside the limit the firm entered.

    The firm's figure is a limit read from the matter's custom fields, where the mapped
    policy-limit field is extracted. Only limits on the same basis (per person or per
    occurrence) are compared. A file can name more than one policy, so the firm's figure
    agrees when any other source states it; only a figure no source confirms carries
    the other values.
    """
    limits = [
        f
        for f in facts
        if f.kind is FactKind.POLICY_LIMIT
        and (f.value_json or {}).get("amount_cents") is not None
    ]
    stated_elsewhere = [f for f in limits if f.source_id not in matter_sources]
    disagreements = 0
    for firm in (f for f in limits if f.source_id in matter_sources):
        value = dict(firm.value_json)
        same_basis = [
            f for f in stated_elsewhere if f.value_json.get("per") == value.get("per")
        ]
        amounts = {f.value_json["amount_cents"] for f in same_basis}
        alternatives: list[dict[str, Any]] = []
        if same_basis and value["amount_cents"] not in amounts:
            alternatives = _first_of_each_amount(same_basis)
            disagreements += 1
        value["alt_values"] = alternatives
        firm.value_json = value
    return disagreements


def _first_of_each_amount(facts: list[Fact]) -> list[dict[str, Any]]:
    seen: dict[int, dict[str, Any]] = {}
    for fact in facts:
        amount = fact.value_json["amount_cents"]
        seen.setdefault(
            amount,
            {
                "amount_cents": amount,
                "source_id": fact.source_id,
                "page_no": fact.page_no,
            },
        )
    return list(seen.values())
