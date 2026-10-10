"""Firm-specific vocabulary, resolved by cached model calls instead of names in code.

Three small mappings run before extraction, because extraction needs to know who the
medical providers are:

- roles: relationship descriptions -> medical provider, insurer, opposing party, other
- fields: custom field names -> canonical KPI slots, and the firm's stage -> a canonical stage
- ledger: non-time activities -> firm cost or the client's medical charge (`ledger.py`)

The result is stored as the `field_mapping` digest (`FieldMappingContent`). Fields that
code can read (case value, specials, incident date, limitation date) and the stage
become `origin = code` facts on the matter source (`matter_fields.py`). The rest of the
custom fields go through record extraction as one input.
"""

import hashlib
import json
import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.digest import llm
from app.digest.ledger import ledger_facts
from app.digest.matter_fields import (
    CustomValue,
    custom_values,
    extraction_text,
    slot_fact,
    stage_facts,
)
from app.digest.payloads import build_payload
from app.digest.records import (
    code_fact,
    name_of,
    replace_facts,
    sources_of,
)
from app.models import (
    Digest,
    DigestKind,
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


@dataclass
class MatterMapping:
    contact_roles: dict[int, ContactRole]
    contact_names: dict[int, str]
    field_slots: dict[int, FieldSlot]
    matter: Source | None
    # Custom fields the record extractor reads, as one text, with the matter as source.
    extraction_text: str
    # Mapping calls that failed this run; the previous mapping stood in for each.
    errors: list[str] = field(default_factory=list)

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
    # A failed call must not wipe what the last good mapping produced: its roles and
    # slots stand in, the facts that need the missing answer are left as they are,
    # and the run records the error. `cli digest --retry-failed` asks the model again.
    previous = _previous_mapping(session, matter_id)
    errors: list[str] = []
    counts: Counter[str] = Counter()

    roles, names = _map_roles(session, matter_id, relationships)
    if roles is None:
        errors.append("Role mapping call failed; kept the previous contact roles")
        roles = dict(previous.contact_roles) if previous else {}
    _add_client(roles, names, matter)

    fields = _map_fields(session, matter_id, matter, values)
    if fields is None:
        errors.append(
            "Field mapping call failed; kept the previous KPI and stage facts"
        )
        slots = dict(previous.field_slots) if previous else {}
    else:
        slots, stage = fields
        if matter is not None:
            facts = stage_facts(matter, stage) + [
                fact for v in values if (fact := slot_fact(v, slots.get(v.field_id)))
            ]
            replace_facts(session, matter, facts, Origin.CODE)
            counts["matter"] = len(facts)
    counts["party"] = _party_facts(session, relationships, roles)
    mapping = MatterMapping(
        contact_roles=roles,
        contact_names=names,
        field_slots=slots,
        matter=matter,
        extraction_text=extraction_text(values, slots),
        errors=errors,
    )
    ledger = ledger_facts(session, matter_id, mapping.providers())
    if ledger is None:
        errors.append("Activity call failed; kept the previous ledger facts")
    else:
        counts.update(ledger)
    _store(session, matter_id, mapping)
    session.commit()
    for error in errors:
        log.warning("Mapping: %s", error)
    log.info(
        "Mapping: %d contacts, %d providers, %d slots, facts %s",
        len(roles),
        len(mapping.providers()),
        len(slots),
        dict(counts),
    )
    return mapping


def _previous_mapping(session: Session, matter_id: int) -> FieldMappingContent | None:
    stored = session.scalars(
        select(Digest).where(
            Digest.matter_id == matter_id, Digest.kind == DigestKind.FIELD_MAPPING
        )
    ).first()
    return FieldMappingContent.model_validate(stored.content_json) if stored else None


def _map_roles(
    session: Session, matter_id: int, relationships: list[Source]
) -> tuple[dict[int, ContactRole] | None, dict[int, str]]:
    """Each related contact's role, or None for the roles when the call failed."""
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
        if not isinstance(result, RoleMapping):
            return None, names
        roles = {
            e.contact_id: ContactRole(e.role)
            for e in result.contacts
            if e.contact_id in contacts
        }
    return roles, names


def _add_client(
    roles: dict[int, ContactRole], names: dict[int, str], matter: Source | None
) -> None:
    client = (matter.raw_json.get("client") or {}) if matter else {}
    if client.get("id"):
        roles[int(client["id"])] = ContactRole.CLIENT
        names[int(client["id"])] = str(client.get("name") or client["id"])


def _map_fields(
    session: Session,
    matter_id: int,
    matter: Source | None,
    values: list[CustomValue],
) -> tuple[dict[int, FieldSlot], CaseStage | None] | None:
    """Custom field slots and the canonical stage, or None when the call failed."""
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
        return None
    known = {v.field_id for v in values}
    slots: dict[int, FieldSlot] = {}
    for entry in result.fields:
        if entry.field_id in known and entry.slot != "none":
            slot = FieldSlot(entry.slot)
            if slot not in slots.values():  # each slot maps to at most one field
                slots[entry.field_id] = slot
    return slots, CaseStage(result.stage) if result.stage else None


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
        fact = code_fact(
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
