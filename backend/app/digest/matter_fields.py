"""Facts code reads from the matter record itself: its stage, and the custom fields
the field mapping assigned to a slot code can read (case value, specials, incident
date, limitation date). The rest of the custom fields go to record extraction as one
text, built here."""

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.digest.payloads import build_payload, to_cents
from app.digest.records import (
    code_fact,
    name_of,
    parse_date,
    sources_of,
)
from app.models import (
    Fact,
    FactKind,
    Source,
    SourceType,
)
from app.schemas import CaseStage, FieldSlot

# Slots whose value code can read. Coverage and policy limits are multi-part free text,
# so those fields go through record extraction instead.
CODE_SLOTS = {
    FieldSlot.CASE_VALUE,
    FieldSlot.MEDICAL_SPECIALS,
    FieldSlot.DATE_OF_INCIDENT,
    FieldSlot.STATUTE_OF_LIMITATIONS,
}


_MONEY = re.compile(
    r"\$?\s?(\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)\s*([kKmM])?"
)


@dataclass
class CustomValue:
    field_id: int  # Clio custom field id: stable, unlike the value's own id
    name: str
    text: str


def custom_values(
    session: Session, matter_id: int, matter: Source | None
) -> list[CustomValue]:
    """The matter's filled-in custom fields, with picklist ids resolved to labels."""
    if matter is None:
        return []
    definitions = {
        int(d.clio_id): d.raw_json
        for d in sources_of(session, matter_id, SourceType.CUSTOM_FIELD)
        if str(d.clio_id).isdigit()
    }
    values = []
    for raw in matter.raw_json.get("custom_field_values") or []:
        field_id = (raw.get("custom_field") or {}).get("id")
        if field_id is None:
            continue
        definition = definitions.get(int(field_id), {})
        text = _value_text(raw, definition)
        if text:
            name = str(raw.get("field_name") or definition.get("name") or field_id)
            values.append(CustomValue(int(field_id), name, text))
    return values


def _value_text(raw: dict[str, Any], definition: dict[str, Any]) -> str:
    options = {
        str(o.get("id")): str(o.get("option"))
        for o in definition.get("picklist_options") or []
    }
    option = raw.get("picklist_option")
    if isinstance(option, dict) and str(option.get("id")) in options:
        return options[str(option["id"])]
    value = raw.get("value")
    if value is None:
        return ""
    if str(value) in options:
        return options[str(value)]
    return str(value).strip()


def stage_facts(matter: Source, stage: CaseStage | None) -> list[Fact]:
    # Clio keeps whatever whitespace the firm typed around a stage name.
    label = (name_of(matter.raw_json.get("matter_stage")) or "").strip()
    status = matter.raw_json.get("status")
    if stage is None and not label:
        return []
    quote = label or str(status or "").strip()
    return [
        code_fact(
            FactKind.CASE_STAGE,
            f"Stage: {label or stage}",
            quote,
            # The day the stage last changed, or no date. `updated_at` is the record's
            # last edit of any kind, which a reader takes for the day the case moved.
            event_date=parse_date(matter.raw_json.get("matter_stage_updated_at")),
            # Inferred when Clio has no stage and the status alone decided it.
            value_json=build_payload(
                FactKind.CASE_STAGE, None, {"stage": stage, "inferred": not label}
            ),
        )
    ]


def slot_fact(value: CustomValue, slot: FieldSlot | None) -> Fact | None:
    """A fact from a field mapped to a slot code can read; None if it cannot be read."""
    if slot not in CODE_SLOTS:
        return None
    if slot in (FieldSlot.CASE_VALUE, FieldSlot.MEDICAL_SPECIALS):
        amounts = parse_money(value.text)
        if not amounts:
            return None
        if slot is FieldSlot.CASE_VALUE:
            payload = {
                "low_cents": min(amounts),
                "high_cents": max(amounts),
                "basis": value.name,
            }
            return code_fact(
                FactKind.CASE_VALUE,
                value.name,
                value.text,
                mentions_strategy=True,
                value_json=build_payload(FactKind.CASE_VALUE, None, payload),
            )
        return code_fact(
            FactKind.MEDICAL_SPECIALS,
            value.name,
            value.text,
            value_json=build_payload(
                FactKind.MEDICAL_SPECIALS, None, {"amount_cents": amounts[0]}
            ),
        )
    day = parse_date(value.text) or _us_date(value.text)
    if day is None:
        return None
    if slot is FieldSlot.STATUTE_OF_LIMITATIONS:
        payload = {
            "deadline_type": "statute_of_limitations",
            "due_at": f"{day.isoformat()}T00:00:00Z",
        }
        return code_fact(
            FactKind.DEADLINE,
            value.name,
            value.text,
            event_date=day,
            value_json=build_payload(FactKind.DEADLINE, None, payload),
        )
    return code_fact(
        FactKind.INCIDENT,
        value.name,
        value.text,
        event_date=day,
        value_json=build_payload(FactKind.INCIDENT, None, {}),
    )


def extraction_text(values: list[CustomValue], slots: dict[int, FieldSlot]) -> str:
    lines = [
        f"{v.name}: {v.text}" for v in values if slots.get(v.field_id) not in CODE_SLOTS
    ]
    if not lines:
        return ""
    return "Type: matter custom fields, as filled in by the firm\n\n" + "\n".join(lines)


def parse_money(text: str) -> list[int]:
    """Dollar amounts in a field value, as cents, in order of appearance."""
    amounts = []
    for number, suffix in _MONEY.findall(text):
        value = Decimal(number.replace(",", ""))
        if suffix.lower() == "k":
            value *= 1000
        elif suffix.lower() == "m":
            value *= 1_000_000
        cents = to_cents(value)
        if cents and cents >= 100:
            amounts.append(cents)
    return amounts


def _us_date(text: str) -> date | None:
    match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if not match:
        return None
    month, day, year = (int(g) for g in match.groups())
    return parse_date(f"{year:04d}-{month:02d}-{day:02d}")
