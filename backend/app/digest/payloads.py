"""Build `facts.value_json` payloads that pass the frozen contract in `schemas.py`.

`validate_payload` rejects unknown keys, so model output is narrowed to the keys the
kind allows before validation, and a key with an invalid value is dropped rather than
losing the whole fact.
"""

from decimal import Decimal, InvalidOperation
from typing import Any, get_args

from pydantic import ValidationError

from app.models import FactKind
from app.schemas import PAYLOAD_BY_KIND, LitigationEventType, validate_payload

# The extraction prompts ask for every sum in dollars. These detail keys carry one,
# and code stores it in the cents field beside it.
MODEL_DOLLAR_KEYS = {"balance": "balance_cents", "high": "high_cents"}

LITIGATION_EVENT_TYPES = set(get_args(LitigationEventType))
# Checked in order, so a recommenced action reads as renewed, not filed, and an
# examination before trial as a deposition, not a trial.
LITIGATION_EVENT_STEMS = (
    ("renew", "renewed"),
    ("recommenc", "renewed"),
    ("refil", "renewed"),
    ("re-fil", "renewed"),
    ("dismiss", "dismissed"),
    ("discontinu", "dismissed"),
    ("answer", "answered"),
    ("deposition", "deposition"),
    ("before trial", "deposition"),
    ("motion", "motion"),
    ("order", "order"),
    ("decision", "order"),
    ("judgment", "order"),
    ("hearing", "hearing"),
    ("trial", "trial"),
    ("served", "served"),
    ("service", "served"),
    ("filed", "filed"),
    ("filing", "filed"),
    ("commenc", "filed"),
)


def model_payload(
    kind: FactKind,
    amount: Any,
    detail: dict[str, Any],
    fallback_label: str | None = None,
) -> dict[str, Any]:
    """Build a payload from extraction output, whose sums are all in dollars.

    The model is never asked for a `*_cents` key, so one it volunteers has an unknown
    unit and is dropped rather than guessed; the dollar keys are converted here.
    """
    values = {
        k: v
        for k, v in detail.items()
        if not k.endswith("_cents") and k not in MODEL_DOLLAR_KEYS
    }
    for key, field in MODEL_DOLLAR_KEYS.items():
        cents = to_cents(detail.get(key))
        if cents is not None:
            values[field] = cents
    return build_payload(kind, amount, values, fallback_label)


def build_payload(
    kind: FactKind,
    amount: Any,
    detail: dict[str, Any],
    fallback_label: str | None = None,
) -> dict[str, Any]:
    fields = PAYLOAD_BY_KIND[kind].model_fields
    values = {k: v for k, v in detail.items() if k in fields and v is not None}
    cents = to_cents(amount)
    if cents is not None:
        if kind is FactKind.CASE_VALUE:
            values.setdefault("low_cents", cents)
        elif "amount_cents" in fields:
            values.setdefault("amount_cents", cents)
    if kind is FactKind.OTHER and "detail" not in values:
        text = detail.get("description") or fallback_label
        if text:
            values["detail"] = str(text)
    if kind is FactKind.LITIGATION_EVENT:
        if "detail" not in values and detail.get("description"):
            values["detail"] = str(detail["description"])
        values["event"] = litigation_event_type(values.get("event"))
    if kind is FactKind.STATUS_CHANGE and not values.get("label"):
        values["label"] = fallback_label or "Stage changed"
    if kind is FactKind.TASK:
        values["status"] = task_status(values.get("status"))
    if kind is FactKind.CLIENT_CONTACT and "channel" in values:
        values["channel"] = contact_channel(str(values["channel"]))
    for _attempt in range(len(values) + 1):
        try:
            return validate_payload(kind, values)
        except ValidationError as error:
            bad = {str(e["loc"][0]) for e in error.errors() if e.get("loc")}
            required = {name for name, f in fields.items() if f.is_required()}
            if not bad or bad <= required:
                raise
            for key in bad - required:
                values.pop(key, None)
    return validate_payload(kind, values)


def task_status(value: Any) -> str:
    text = str(value or "").lower()
    return "complete" if text in {"complete", "completed", "done"} else "open"


def litigation_event_type(value: Any) -> str:
    """One of the contract's event types; a model's own wording is matched by stem."""
    text = str(value or "").strip().lower()
    if text in LITIGATION_EVENT_TYPES:
        return text
    for stem, event in LITIGATION_EVENT_STEMS:
        if stem in text:
            return event
    return "other"


def contact_channel(value: str) -> str:
    text = value.lower()
    for channel in ("email", "phone", "text", "meeting", "letter"):
        if channel in text:
            return channel
    if "call" in text:
        return "phone"
    return "other"


def to_cents(amount: Any) -> int | None:
    if amount is None or amount == "":
        return None
    try:
        value = Decimal(str(amount).replace("$", "").replace(",", "").strip())
    except InvalidOperation:
        return None
    return int((value * 100).to_integral_value())
