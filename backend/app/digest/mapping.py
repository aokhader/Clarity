"""Firm-specific vocabulary, resolved by cached model calls instead of names in code.

Three small mappings run before extraction, because extraction needs to know who the
medical providers are:

- roles: relationship descriptions -> medical provider, insurer, opposing party, other
- fields: custom field names -> canonical KPI slots, and the firm's stage -> a canonical stage
- ledger: non-time activities -> firm cost or the client's medical charge

The result is stored as the `field_mapping` digest (`FieldMappingContent`). Fields that
code can read (case value, specials, incident date, limitation date) and the stage
become `origin = code` facts on the matter source. The rest of the custom fields go
through record extraction as one input.
"""

import hashlib
import json
import logging
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.digest import llm
from app.digest.payloads import build_payload, to_cents
from app.digest.records import name_of, parse_date, replace_facts, sources_of
from app.digest.verify import resolve_provider
from app.models import (
    Confidence,
    Digest,
    DigestKind,
    Fact,
    FactKind,
    Origin,
    Source,
    SourceType,
)
from app.schemas import CaseStage, ContactRole, FieldMappingContent, FieldSlot

log = logging.getLogger(__name__)

ModelRole = Literal["medical_provider", "insurer", "opposing_party", "other"]
ModelSlot = Literal[
    "case_value",
    "medical_specials",
    "coverage",
    "policy_limit",
    "date_of_incident",
    "statute_of_limitations",
    "none",
]
ModelStage = Literal[
    "intake",
    "treating",
    "treatment_complete",
    "demand",
    "negotiation",
    "litigation",
    "settled",
    "closed",
]
# Slots whose value code can read. Coverage and policy limits are multi-part free text,
# so those fields go through record extraction instead.
CODE_SLOTS = {
    FieldSlot.CASE_VALUE,
    FieldSlot.MEDICAL_SPECIALS,
    FieldSlot.DATE_OF_INCIDENT,
    FieldSlot.STATUTE_OF_LIMITATIONS,
}
TIME_ACTIVITY_TYPES = {"TimeEntry"}
QUOTE_LIMIT = 300
_MONEY = re.compile(
    r"\$?\s?(\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)\s*([kKmM])?"
)


class RoleEntry(BaseModel):
    contact_id: int
    role: ModelRole


class RoleMapping(BaseModel):
    contacts: list[RoleEntry]


class FieldEntry(BaseModel):
    field_id: int
    slot: ModelSlot


class FieldMapping(BaseModel):
    fields: list[FieldEntry]
    stage: ModelStage | None = None


class LedgerEntry(BaseModel):
    activity_id: int
    is_medical_charge: bool
    provider_contact_id: int | None = None
    provider_name_as_written: str | None = None


class LedgerMapping(BaseModel):
    activities: list[LedgerEntry]


@dataclass
class CustomValue:
    field_id: int  # Clio custom field id: stable, unlike the value's own id
    name: str
    text: str


@dataclass
class MatterMapping:
    contact_roles: dict[int, ContactRole]
    contact_names: dict[int, str]
    field_slots: dict[int, FieldSlot]
    matter: Source | None
    # Custom fields the record extractor reads, as one text, with the matter as source.
    extraction_text: str

    def providers(self) -> dict[int, str]:
        return {
            contact_id: self.contact_names.get(contact_id, str(contact_id))
            for contact_id, role in self.contact_roles.items()
            if role is ContactRole.MEDICAL_PROVIDER
        }


def build_mapping(session: Session, matter_id: int) -> MatterMapping:
    matters = sources_of(session, matter_id, SourceType.MATTER)
    matter = matters[0] if matters else None
    relationships = sources_of(session, matter_id, SourceType.RELATIONSHIP)
    values = custom_values(session, matter_id, matter)

    roles, names = _map_roles(session, matter_id, matter, relationships)
    slots, stage = _map_fields(session, matter_id, matter, values)
    counts: Counter[str] = Counter()
    if matter is not None:
        facts = _stage_facts(matter, stage) + [
            fact for v in values if (fact := _slot_fact(v, slots.get(v.field_id)))
        ]
        replace_facts(session, matter, facts, Origin.CODE)
        counts["matter"] = len(facts)
    counts["party"] = _party_facts(session, relationships, roles)
    mapping = MatterMapping(
        contact_roles=roles,
        contact_names=names,
        field_slots=slots,
        matter=matter,
        extraction_text=_extraction_text(values, slots),
    )
    counts.update(_ledger_facts(session, matter_id, mapping.providers()))
    _store(session, matter_id, mapping)
    session.commit()
    log.info(
        "Mapping: %d contacts, %d providers, %d slots, facts %s",
        len(roles),
        len(mapping.providers()),
        len(slots),
        dict(counts),
    )
    return mapping


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


def _map_roles(
    session: Session,
    matter_id: int,
    matter: Source | None,
    relationships: list[Source],
) -> tuple[dict[int, ContactRole], dict[int, str]]:
    contacts: dict[int, dict[str, Any]] = {}
    for relationship in relationships:
        contact = relationship.raw_json.get("contact") or {}
        if contact.get("id"):
            contacts[int(contact["id"])] = {
                "contact_id": int(contact["id"]),
                "name": contact.get("name"),
                "description": relationship.raw_json.get("description"),
            }
    names = {cid: str(c["name"] or cid) for cid, c in contacts.items()}
    roles: dict[int, ContactRole] = {}
    if contacts:
        result = llm.call(
            session,
            llm.ModelRequest(
                purpose="map_roles",
                role="merge",
                prompt=llm.load_prompt("map_roles"),
                user_text=json.dumps({"contacts": list(contacts.values())}, indent=1),
                output=RoleMapping,
                matter_id=matter_id,
            ),
        )
        if isinstance(result, RoleMapping):
            roles = {
                e.contact_id: ContactRole(e.role)
                for e in result.contacts
                if e.contact_id in contacts
            }
    client = (matter.raw_json.get("client") or {}) if matter else {}
    if client.get("id"):
        roles[int(client["id"])] = ContactRole.CLIENT
        names[int(client["id"])] = str(client.get("name") or client["id"])
    return roles, names


def _map_fields(
    session: Session,
    matter_id: int,
    matter: Source | None,
    values: list[CustomValue],
) -> tuple[dict[int, FieldSlot], CaseStage | None]:
    if matter is None:
        return {}, None
    payload = {
        "fields": [
            {"field_id": v.field_id, "name": v.name, "value": v.text[:400]}
            for v in values
        ],
        "matter_stage": name_of(matter.raw_json.get("matter_stage")),
        "matter_status": matter.raw_json.get("status"),
    }
    result = llm.call(
        session,
        llm.ModelRequest(
            purpose="map_fields",
            role="merge",
            prompt=llm.load_prompt("map_fields"),
            user_text=json.dumps(payload, indent=1),
            output=FieldMapping,
            matter_id=matter_id,
        ),
    )
    if not isinstance(result, FieldMapping):
        return {}, None
    known = {v.field_id for v in values}
    slots: dict[int, FieldSlot] = {}
    for entry in result.fields:
        if entry.field_id in known and entry.slot != "none":
            slot = FieldSlot(entry.slot)
            if slot not in slots.values():  # each slot maps to at most one field
                slots[entry.field_id] = slot
    return slots, CaseStage(result.stage) if result.stage else None


def _code_fact(kind: FactKind, title: str, quote: str, **values: Any) -> Fact:
    return Fact(
        kind=kind,
        title=title[:120],
        quote=quote[:QUOTE_LIMIT],
        confidence=Confidence.HIGH,
        verified=True,
        significance=0,
        mentions_strategy=values.pop("mentions_strategy", False),
        **values,
    )


def _stage_facts(matter: Source, stage: CaseStage | None) -> list[Fact]:
    label = name_of(matter.raw_json.get("matter_stage"))
    status = matter.raw_json.get("status")
    if stage is None and not label:
        return []
    quote = label or str(status or "")
    return [
        _code_fact(
            FactKind.CASE_STAGE,
            f"Stage: {label or stage}",
            quote,
            event_date=parse_date(matter.raw_json.get("updated_at")),
            # Inferred when Clio has no stage and the status alone decided it.
            value_json=build_payload(
                FactKind.CASE_STAGE, None, {"stage": stage, "inferred": not label}
            ),
        )
    ]


def _slot_fact(value: CustomValue, slot: FieldSlot | None) -> Fact | None:
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
            return _code_fact(
                FactKind.CASE_VALUE,
                value.name,
                value.text,
                mentions_strategy=True,
                value_json=build_payload(FactKind.CASE_VALUE, None, payload),
            )
        return _code_fact(
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
        return _code_fact(
            FactKind.DEADLINE,
            value.name,
            value.text,
            event_date=day,
            value_json=build_payload(FactKind.DEADLINE, None, payload),
        )
    return _code_fact(
        FactKind.INCIDENT,
        value.name,
        value.text,
        event_date=day,
        value_json=build_payload(FactKind.INCIDENT, None, {}),
    )


def _extraction_text(values: list[CustomValue], slots: dict[int, FieldSlot]) -> str:
    lines = [
        f"{v.name}: {v.text}" for v in values if slots.get(v.field_id) not in CODE_SLOTS
    ]
    if not lines:
        return ""
    return "Type: matter custom fields, as filled in by the firm\n\n" + "\n".join(lines)


def _party_facts(
    session: Session, relationships: list[Source], roles: dict[int, ContactRole]
) -> int:
    count = 0
    for relationship in relationships:
        contact = relationship.raw_json.get("contact") or {}
        if not contact.get("id"):
            continue
        contact_id = int(contact["id"])
        role = roles.get(contact_id, ContactRole.OTHER)
        description = str(relationship.raw_json.get("description") or role.value)
        fact = _code_fact(
            FactKind.PARTY,
            f"{contact.get('name')}: {description}",
            description,
            value_json=build_payload(FactKind.PARTY, None, {"role": role.value}),
            provider_contact_id=contact_id
            if role is ContactRole.MEDICAL_PROVIDER
            else None,
        )
        replace_facts(session, relationship, [fact], Origin.CODE)
        count += 1
    return count


def _ledger_facts(
    session: Session, matter_id: int, providers: dict[int, str]
) -> Counter[str]:
    counts: Counter[str] = Counter()
    activities = [
        a
        for a in sources_of(session, matter_id, SourceType.ACTIVITY)
        if a.raw_json.get("type") not in TIME_ACTIVITY_TYPES
    ]
    if not activities:
        return counts
    entries = [
        {
            "activity_id": a.id,
            "type": a.raw_json.get("type"),
            "date": a.raw_json.get("date"),
            "amount": str(activity_amount(a.raw_json)),
            "category": name_of(a.raw_json.get("expense_category")),
            "vendor": name_of(a.raw_json.get("vendor")),
            "note": str(a.raw_json.get("note") or "")[:500],
        }
        for a in activities
    ]
    known = [{"contact_id": cid, "name": name} for cid, name in providers.items()]
    result = llm.call(
        session,
        llm.ModelRequest(
            purpose="classify_activities",
            role="merge",
            prompt=llm.load_prompt("classify_activities"),
            user_text=json.dumps(
                {"known_providers": known, "entries": entries}, indent=1
            ),
            output=LedgerMapping,
            matter_id=matter_id,
        ),
    )
    decisions = (
        {e.activity_id: e for e in result.activities}
        if isinstance(result, LedgerMapping)
        else {}
    )
    for activity in activities:
        fact = _ledger_fact(activity, decisions.get(activity.id), providers)
        replace_facts(session, activity, [fact], Origin.CODE)
        counts[fact.kind.value] += 1
    return counts


def activity_amount(raw: dict[str, Any]) -> Decimal:
    """`total` covers draft, billable, and billed amounts; non-billable is separate."""
    return Decimal(str(raw.get("total") or 0)) + Decimal(
        str(raw.get("non_billable_total") or 0)
    )


def _ledger_fact(
    activity: Source, decision: LedgerEntry | None, providers: dict[int, str]
) -> Fact:
    raw = activity.raw_json
    category = name_of(raw.get("expense_category"))
    note = str(raw.get("note") or "")
    label = category or note.split(";")[0].strip() or "Expense"
    is_medical = bool(decision and decision.is_medical_charge)
    kind = FactKind.MEDICAL_BILL if is_medical else FactKind.EXPENSE
    provider_id = None
    if is_medical and decision:
        if decision.provider_contact_id in providers:
            provider_id = decision.provider_contact_id
        provider_id = provider_id or resolve_provider(
            decision.provider_name_as_written, providers
        )
    detail = (
        {}
        if is_medical
        else {"category": category, "vendor": name_of(raw.get("vendor"))}
    )
    return Fact(
        kind=kind,
        title=label[:120],
        quote=(note or category or label)[:QUOTE_LIMIT],
        event_date=parse_date(raw.get("date")),
        value_json=build_payload(kind, activity_amount(raw), detail),
        provider_contact_id=provider_id,
        # The amount is exact; only the medical-or-firm split came from a model.
        confidence=Confidence.HIGH if decision else Confidence.MEDIUM,
        verified=decision is not None,
        significance=0,
        mentions_strategy=False,
    )


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


def _store(session: Session, matter_id: int, mapping: MatterMapping) -> None:
    content = FieldMappingContent(
        contact_roles=mapping.contact_roles, field_slots=mapping.field_slots
    ).model_dump(mode="json")
    input_hash = hashlib.sha256(
        json.dumps(content, sort_keys=True).encode()
    ).hexdigest()
    existing = session.scalars(
        select(Digest).where(
            Digest.matter_id == matter_id, Digest.kind == DigestKind.FIELD_MAPPING
        )
    ).first()
    if existing is None:
        existing = Digest(
            matter_id=matter_id,
            kind=DigestKind.FIELD_MAPPING,
            content_json=content,
            input_hash=input_hash,
            model="merge",
        )
        session.add(existing)
    existing.content_json = content
    existing.input_hash = input_hash
