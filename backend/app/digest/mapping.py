"""Firm-specific vocabulary, resolved by cached model calls instead of names in code.

Three small mappings run before extraction, because extraction needs to know who the
medical providers are:

- roles: relationship descriptions -> provider, insurer, opposing party, ...
- fields: custom field names -> canonical KPI slots (case value, specials, ...)
- activities: non-time ledger entries -> firm cost or the client's medical charge

The result is stored as the `field_mapping` digest, and becomes facts with the
relationship, custom field, or activity as their source.
"""

import hashlib
import json
import logging
import re
from collections import Counter
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.digest import llm
from app.digest.payloads import build_payload, to_cents
from app.digest.records import (
    custom_field_name,
    custom_field_value,
    name_of,
    parse_date,
    replace_facts,
    sources_of,
)
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

log = logging.getLogger(__name__)

Role = Literal[
    "medical_provider",
    "insurer",
    "opposing_party",
    "opposing_counsel",
    "lienholder",
    "defense_examiner",
    "other",
]
Slot = Literal[
    "case_value",
    "medical_specials",
    "coverage",
    "policy_limit",
    "date_of_incident",
    "statute_of_limitations",
    "none",
]
# Slots whose value code can read directly. Coverage and policy limits are free text
# with several parts, so those fields go through record extraction instead.
CODE_SLOTS = {
    "case_value",
    "medical_specials",
    "date_of_incident",
    "statute_of_limitations",
}
TIME_ACTIVITY_TYPES = {"TimeEntry"}
_MONEY = re.compile(
    r"\$?\s?(\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)\s*([kKmM])?"
)


class RoleEntry(BaseModel):
    contact_id: int
    role: Role


class RoleMapping(BaseModel):
    contacts: list[RoleEntry]


class FieldEntry(BaseModel):
    field_id: int
    slot: Slot


class FieldMapping(BaseModel):
    fields: list[FieldEntry]


class ActivityEntry(BaseModel):
    activity_id: int
    is_medical_charge: bool
    provider_contact_id: int | None = None
    provider_name_as_written: str | None = None


class ActivityMapping(BaseModel):
    activities: list[ActivityEntry]


class MatterMapping(BaseModel):
    roles: dict[int, Role]
    contact_names: dict[int, str]
    slots: dict[int, Slot]  # source id of the custom field -> slot

    def providers(self) -> dict[int, str]:
        return {
            contact_id: self.contact_names.get(contact_id, str(contact_id))
            for contact_id, role in self.roles.items()
            if role == "medical_provider"
        }

    def extraction_field_ids(self) -> set[int]:
        """Custom fields the record extractor should read (everything code cannot)."""
        return {
            source_id
            for source_id, slot in self.slots.items()
            if slot not in CODE_SLOTS
        }


def build_mapping(session: Session, matter_id: int) -> MatterMapping:
    relationships = sources_of(session, matter_id, SourceType.RELATIONSHIP)
    fields = sources_of(session, matter_id, SourceType.CUSTOM_FIELD)
    activities = [
        a
        for a in sources_of(session, matter_id, SourceType.ACTIVITY)
        if a.raw_json.get("type") not in TIME_ACTIVITY_TYPES
    ]
    roles, names = _map_roles(session, matter_id, relationships)
    slots = _map_fields(session, matter_id, fields)
    mapping = MatterMapping(roles=roles, contact_names=names, slots=slots)

    counts: Counter[str] = Counter()
    counts["party"] = _party_facts(session, relationships, roles)
    counts["kpi"] = _slot_facts(session, fields, slots)
    counts.update(_activity_facts(session, matter_id, activities, mapping.providers()))
    _store(session, matter_id, mapping)
    session.commit()
    log.info(
        "Mapping: %d contacts, %d fields, %d providers, facts %s",
        len(roles),
        len(slots),
        len(mapping.providers()),
        dict(counts),
    )
    return mapping


def load_mapping(session: Session, matter_id: int) -> MatterMapping | None:
    digest = session.scalars(
        select(Digest)
        .where(Digest.matter_id == matter_id, Digest.kind == DigestKind.FIELD_MAPPING)
        .order_by(Digest.id.desc())
    ).first()
    return MatterMapping.model_validate(digest.content_json) if digest else None


def _map_roles(
    session: Session, matter_id: int, relationships: list[Source]
) -> tuple[dict[int, Role], dict[int, str]]:
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
    if not contacts:
        return {}, names
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
    roles: dict[int, Role] = {}
    if isinstance(result, RoleMapping):
        roles = {
            e.contact_id: e.role for e in result.contacts if e.contact_id in contacts
        }
    return roles, names


def _map_fields(
    session: Session, matter_id: int, fields: list[Source]
) -> dict[int, Slot]:
    if not fields:
        return {}
    payload = [
        {
            "field_id": f.id,
            "name": custom_field_name(f.raw_json),
            "value": custom_field_value(f.raw_json)[:400],
        }
        for f in fields
    ]
    result = llm.call(
        session,
        llm.ModelRequest(
            purpose="map_fields",
            role="merge",
            prompt=llm.load_prompt("map_fields"),
            user_text=json.dumps({"fields": payload}, indent=1),
            output=FieldMapping,
            matter_id=matter_id,
        ),
    )
    slots: dict[int, Slot] = {f.id: "none" for f in fields}
    if isinstance(result, FieldMapping):
        for entry in result.fields:
            if entry.field_id in slots:
                slots[entry.field_id] = entry.slot
    return slots


def _party_facts(
    session: Session, relationships: list[Source], roles: dict[int, Role]
) -> int:
    count = 0
    for relationship in relationships:
        contact = relationship.raw_json.get("contact") or {}
        if not contact.get("id"):
            continue
        contact_id = int(contact["id"])
        role = roles.get(contact_id, "other")
        description = str(relationship.raw_json.get("description") or role)
        fact = Fact(
            kind=FactKind.PARTY,
            title=f"{contact.get('name')}: {description}"[:120],
            quote=description[:300],
            value_json=build_payload(FactKind.PARTY, None, {"role": role}),
            provider_contact_id=contact_id if role == "medical_provider" else None,
            confidence=Confidence.HIGH,
            verified=True,
            significance=0,
            mentions_strategy=False,
        )
        replace_facts(session, relationship, [fact], Origin.CODE)
        count += 1
    return count


def _slot_facts(session: Session, fields: list[Source], slots: dict[int, Slot]) -> int:
    count = 0
    for field in fields:
        slot = slots.get(field.id, "none")
        facts = _slot_fact(field, slot) if slot in CODE_SLOTS else []
        replace_facts(session, field, facts, Origin.CODE)
        count += len(facts)
    return count


def _slot_fact(field: Source, slot: Slot) -> list[Fact]:
    """Turn a field mapped to a code slot into a fact; an unreadable value gives none."""
    value = custom_field_value(field.raw_json)
    name = custom_field_name(field.raw_json)
    common = {
        "quote": value[:300],
        "confidence": Confidence.HIGH,
        "verified": True,
        "significance": 0,
        "mentions_strategy": False,
    }
    if slot in ("case_value", "medical_specials"):
        amounts = parse_money(value)
        if not amounts:
            return []
        if slot == "case_value":
            payload = {
                "low_cents": min(amounts),
                "high_cents": max(amounts),
                "basis": name,
                "slot": slot,
            }
            return [
                Fact(
                    kind=FactKind.CASE_VALUE,
                    title=name,
                    value_json=build_payload(FactKind.CASE_VALUE, None, payload),
                    **{**common, "mentions_strategy": True},
                )
            ]
        payload = {"amount_cents": amounts[0], "slot": slot}
        return [
            Fact(
                kind=FactKind.OTHER,
                title=name,
                value_json=build_payload(FactKind.OTHER, None, payload),
                **common,
            )
        ]
    day = parse_date(value) or _us_date(value)
    if day is None:
        return []
    if slot == "statute_of_limitations":
        payload = {
            "deadline_type": "statute_of_limitations",
            "due_at": day.isoformat(),
            "slot": slot,
        }
        return [
            Fact(
                kind=FactKind.DEADLINE,
                title=name,
                event_date=day,
                value_json=build_payload(FactKind.DEADLINE, None, payload),
                **common,
            )
        ]
    return [
        Fact(
            kind=FactKind.OTHER,
            title=name,
            event_date=day,
            value_json=build_payload(FactKind.OTHER, None, {"slot": slot}),
            **common,
        )
    ]


def _activity_facts(
    session: Session,
    matter_id: int,
    activities: list[Source],
    providers: dict[int, str],
) -> Counter[str]:
    counts: Counter[str] = Counter()
    if not activities:
        return counts
    entries = [
        {
            "activity_id": a.id,
            "type": a.raw_json.get("type"),
            "date": a.raw_json.get("date"),
            "total": a.raw_json.get("total"),
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
            output=ActivityMapping,
            matter_id=matter_id,
        ),
    )
    decisions = (
        {e.activity_id: e for e in result.activities}
        if isinstance(result, ActivityMapping)
        else {}
    )
    for activity in activities:
        decision = decisions.get(activity.id)
        fact = _activity_fact(activity, decision, providers)
        replace_facts(session, activity, [fact], Origin.CODE)
        counts[fact.kind.value] += 1
    return counts


def _activity_fact(
    activity: Source, decision: ActivityEntry | None, providers: dict[int, str]
) -> Fact:
    raw = activity.raw_json
    category = name_of(raw.get("expense_category"))
    note = str(raw.get("note") or "")
    label = category or note.split(";")[0] or "Expense"
    quote = note or category or label
    amount = raw.get("total")
    is_medical = bool(decision and decision.is_medical_charge)
    kind = FactKind.MEDICAL_BILL if is_medical else FactKind.EXPENSE
    provider_id = None
    if is_medical and decision:
        provider_id = (
            decision.provider_contact_id
            if decision.provider_contact_id in providers
            else None
        )
        provider_id = provider_id or resolve_provider(
            decision.provider_name_as_written, providers
        )
    detail: dict[str, Any] = (
        {}
        if is_medical
        else {"category": category, "vendor": name_of(raw.get("vendor"))}
    )
    return Fact(
        kind=kind,
        title=label[:120],
        quote=quote[:300],
        event_date=parse_date(raw.get("date")),
        value_json=build_payload(
            kind, amount, {**detail, "ledger_type": raw.get("type")}
        ),
        provider_contact_id=provider_id,
        # The amount is exact; only the medical/firm split came from a model.
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


def _us_date(text: str):
    match = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", text)
    if not match:
        return None
    month, day, year = (int(g) for g in match.groups())
    return parse_date(f"{year:04d}-{month:02d}-{day:02d}")


def _store(session: Session, matter_id: int, mapping: MatterMapping) -> None:
    content = mapping.model_dump(mode="json")
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
            model="mixed",
        )
        session.add(existing)
    existing.content_json = content
    existing.input_hash = input_hash
