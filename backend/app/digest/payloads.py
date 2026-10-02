"""`facts.value_json` payloads, one model per fact kind, as listed in docs/architecture.md.

The architecture asks for these in `schemas.py`; M0 has not written them yet, so the
pipeline validates against this copy. When they land in `schemas.py`, this module
should import them from there instead. Money is integer cents throughout.
"""

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from app.models import FactKind

WaitingOn = Literal["firm", "client", "provider", "insurer", "court", "other"]


class _Payload(BaseModel):
    model_config = ConfigDict(extra="allow")
    alt_values: list[Any] | None = None
    corroborating_source_ids: list[int] | None = None


class CaseStage(_Payload):
    stage: str | None = None
    inferred: bool = False


class StatusChange(_Payload):
    from_stage: str | None = None
    to_stage: str | None = None
    label: str | None = None


class Injury(_Payload):
    body_part: str | None = None
    description: str | None = None
    severity: str | None = None


class TreatmentVisit(_Payload):
    visit_type: str | None = None


class Money(_Payload):
    amount_cents: int | None = None
    balance_cents: int | None = None


class RecordsReceived(_Payload):
    description: str | None = None
    page_count: int | None = None


class RecordRequest(_Payload):
    description: str | None = None
    status: Literal["open", "fulfilled"] | None = None


class Coverage(_Payload):
    carrier: str | None = None
    coverage_type: str | None = None
    confirmed: bool | None = None


class PolicyLimit(_Payload):
    amount_cents: int | None = None
    per: Literal["person", "occurrence"] | None = None


class CaseValue(_Payload):
    low_cents: int | None = None
    high_cents: int | None = None
    basis: str | None = None


class Liability(_Payload):
    assessment: str | None = None


class Negotiation(_Payload):
    amount_cents: int | None = None
    party: str | None = None


class Expense(_Payload):
    amount_cents: int | None = None
    category: str | None = None
    vendor: str | None = None


class Deadline(_Payload):
    deadline_type: str | None = None
    due_at: str | None = None


class Task(_Payload):
    status: str | None = None
    due_at: str | None = None
    assignee: str | None = None
    waiting_on: WaitingOn | None = None


class ClientContact(_Payload):
    channel: str | None = None
    direction: str | None = None


class Party(_Payload):
    role: str | None = None


class Other(_Payload):
    pass


PAYLOADS: dict[FactKind, type[_Payload]] = {
    FactKind.CASE_STAGE: CaseStage,
    FactKind.STATUS_CHANGE: StatusChange,
    FactKind.INJURY: Injury,
    FactKind.DIAGNOSIS: Injury,
    FactKind.TREATMENT_VISIT: TreatmentVisit,
    FactKind.MEDICAL_BILL: Money,
    FactKind.LIEN: Money,
    FactKind.RECORDS_RECEIVED: RecordsReceived,
    FactKind.RECORD_REQUEST: RecordRequest,
    FactKind.COVERAGE: Coverage,
    FactKind.POLICY_LIMIT: PolicyLimit,
    FactKind.CASE_VALUE: CaseValue,
    FactKind.LIABILITY: Liability,
    FactKind.DEMAND: Negotiation,
    FactKind.OFFER: Negotiation,
    FactKind.SETTLEMENT: Negotiation,
    FactKind.EXPENSE: Expense,
    FactKind.DEADLINE: Deadline,
    FactKind.TASK: Task,
    FactKind.CLIENT_CONTACT: ClientContact,
    FactKind.PARTY: Party,
    FactKind.OTHER: Other,
}

MONEY_KINDS = {
    FactKind.MEDICAL_BILL,
    FactKind.LIEN,
    FactKind.POLICY_LIMIT,
    FactKind.DEMAND,
    FactKind.OFFER,
    FactKind.SETTLEMENT,
    FactKind.EXPENSE,
}


def build_payload(
    kind: FactKind, amount: Decimal | float | None, detail: dict[str, Any]
) -> dict[str, Any]:
    """Validate a kind's payload, folding a top-level amount into the right key."""
    values = dict(detail)
    cents = to_cents(amount)
    if cents is not None:
        if kind is FactKind.CASE_VALUE:
            values.setdefault("low_cents", cents)
        elif kind in MONEY_KINDS:
            values.setdefault("amount_cents", cents)
    model = PAYLOADS[kind].model_validate(values)
    return model.model_dump(mode="json", exclude_none=True)


def to_cents(amount: Any) -> int | None:
    if amount is None or amount == "":
        return None
    try:
        value = Decimal(str(amount).replace("$", "").replace(",", "").strip())
    except InvalidOperation:
        return None
    return int((value * 100).to_integral_value())


def iso(value: date | datetime | str | None) -> str | None:
    if value is None:
        return None
    return value if isinstance(value, str) else value.isoformat()
