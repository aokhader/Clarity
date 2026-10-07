"""Who to call next: the people the matter's open items are waiting on, with numbers.

An overdue or waiting item names whom it waits on: a provider by contact, or the client
or the insurer by role. Each person is listed once, for their most pressing item, with
the phone number synced from Clio when there is one. Names and numbers typed into
Clarity (D15) follow. "Last contact" is the latest record of talking with the person,
a Clio communication or a call from Clarity, and is given only with a fact to cite.
"""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Call, CallNumber, Digest, DigestKind, Fact, Source, SourceType
from app.schemas import (
    CallRole,
    CallTargetOut,
    ContactRole,
    FactOut,
    FactRef,
    FieldMappingContent,
)
from app.services.clio_records import RawCommunication, RawContact, RawMatter
from app.services.fact_views import fact_ref, renderable_facts
from app.services.matter_queries import matter_actions

CONTACT_PREFIX = "contact:"
ENTERED_PREFIX = "entered:"

_ROLE_BY_CONTACT_ROLE: dict[ContactRole, CallRole] = {
    ContactRole.CLIENT: "client",
    ContactRole.MEDICAL_PROVIDER: "provider",
    ContactRole.INSURER: "insurer",
}


class UnknownTarget(LookupError):
    pass


@dataclass(frozen=True)
class _Due:
    """An open item and the contact it waits on."""

    contact_id: int
    role: CallRole
    item: FactOut


def call_targets(session: Session, matter_id: int, today: date) -> list[CallTargetOut]:
    """Contacts with open items, most pressing first, then numbers typed into Clarity."""
    targets: list[CallTargetOut] = []
    seen: set[int] = set()
    for due in _due_items(session, matter_id, today):
        if due.contact_id in seen:
            continue
        seen.add(due.contact_id)
        targets.append(
            _contact_target(
                session, matter_id, due.contact_id, due.role, today, due.item
            )
        )
    numbers = session.scalars(
        select(CallNumber)
        .where(CallNumber.matter_id == matter_id)
        .order_by(CallNumber.id)
    )
    targets += [_entered_target(session, n, today) for n in numbers]
    return targets


def target_for(
    session: Session, matter_id: int, target_id: str, today: date
) -> CallTargetOut:
    """The target behind an id from the list, or a typed number. Raises UnknownTarget."""
    if target_id.startswith(ENTERED_PREFIX):
        number = session.get(CallNumber, _id_after(target_id, ENTERED_PREFIX))
        if number is None or number.matter_id != matter_id:
            raise UnknownTarget(f"no number {target_id} on matter {matter_id}")
        return _entered_target(session, number, today)
    if target_id.startswith(CONTACT_PREFIX):
        contact_id = _id_after(target_id, CONTACT_PREFIX)
        if _contact(session, matter_id, contact_id) is None:
            raise UnknownTarget(f"no contact {contact_id} on matter {matter_id}")
        item = next(
            (
                d.item
                for d in _due_items(session, matter_id, today)
                if d.contact_id == contact_id
            ),
            None,
        )
        role = _roles(session, matter_id).get(contact_id, "other")
        return _contact_target(session, matter_id, contact_id, role, today, item)
    raise UnknownTarget(f"unknown target {target_id!r}")


def add_number(
    session: Session, matter_id: int, name: str, phone: str, today: date
) -> CallTargetOut:
    number = CallNumber(matter_id=matter_id, name=name.strip(), phone=phone.strip())
    session.add(number)
    session.commit()
    return _entered_target(session, number, today)


# --- The items and whom they wait on -----------------------------------------------


def _due_items(session: Session, matter_id: int, today: date) -> list[_Due]:
    actions = matter_actions(session, matter_id, today)
    roles = _roles(session, matter_id)
    client = _client_id(session, matter_id)
    insurers = sorted(cid for cid, role in roles.items() if role == "insurer")
    due = []
    for item in [*actions.overdue, *actions.waiting_on_others]:
        waiting_on = item.value.get("waiting_on")
        if item.provider_contact_id is not None:
            due.append(_Due(item.provider_contact_id, "provider", item))
        elif waiting_on == "client" and client is not None:
            due.append(_Due(client, "client", item))
        elif waiting_on == "insurer" and insurers:
            due.append(_Due(insurers[0], "insurer", item))
    return due


def _roles(session: Session, matter_id: int) -> dict[int, CallRole]:
    stored = session.scalars(
        select(Digest)
        .where(Digest.matter_id == matter_id, Digest.kind == DigestKind.FIELD_MAPPING)
        .order_by(Digest.created_at.desc(), Digest.id.desc())
    ).first()
    roles: dict[int, CallRole] = {}
    if stored is not None:
        mapping = FieldMappingContent.model_validate(stored.content_json)
        roles = {
            cid: _ROLE_BY_CONTACT_ROLE.get(role, "other")
            for cid, role in mapping.contact_roles.items()
        }
    if (client := _client_id(session, matter_id)) is not None:
        roles[client] = "client"
    return roles


def _client_id(session: Session, matter_id: int) -> int | None:
    source = session.scalars(
        select(Source).where(
            Source.matter_id == matter_id, Source.clio_type == SourceType.MATTER
        )
    ).first()
    if source is None:
        return None
    client = RawMatter.model_validate(source.raw_json).client
    return int(client.id) if client and client.id is not None else None


# --- Building a target -------------------------------------------------------------


def _contact(session: Session, matter_id: int, contact_id: int) -> RawContact | None:
    source = session.scalars(
        select(Source).where(
            Source.matter_id == matter_id,
            Source.clio_type == SourceType.CONTACT,
            Source.clio_id == str(contact_id),
        )
    ).first()
    return RawContact.model_validate(source.raw_json) if source else None


def _contact_target(
    session: Session,
    matter_id: int,
    contact_id: int,
    role: CallRole,
    today: date,
    item: FactOut | None,
) -> CallTargetOut:
    contact = _contact(session, matter_id, contact_id)
    phone = (
        next((p.number for p in contact.phone_numbers if p.number), None)
        if contact
        else None
    )
    target_id = f"{CONTACT_PREFIX}{contact_id}"
    days, fact = _last_contact(session, matter_id, target_id, contact_id, today)
    return CallTargetOut(
        target_id=target_id,
        name=contact.name if contact else None,
        role=role,
        phone=phone,
        phone_source="clio" if phone else None,
        reason=item.title if item else None,
        reason_fact=_ref(item) if item else None,
        last_contact_days=days,
        last_contact_fact=fact,
    )


def _entered_target(session: Session, number: CallNumber, today: date) -> CallTargetOut:
    target_id = f"{ENTERED_PREFIX}{number.id}"
    days, fact = _last_contact(session, number.matter_id, target_id, None, today)
    return CallTargetOut(
        target_id=target_id,
        name=number.name,
        role="other",
        phone=number.phone,
        phone_source="entered",
        reason=None,
        reason_fact=None,
        last_contact_days=days,
        last_contact_fact=fact,
    )


def _ref(item: FactOut) -> FactRef:
    return FactRef(
        id=item.id,
        source_type=item.source_type,
        page_no=item.page_no,
        confidence=item.confidence,
    )


# --- Last contact ------------------------------------------------------------------


def _last_contact(
    session: Session,
    matter_id: int,
    target_id: str,
    contact_id: int | None,
    today: date,
) -> tuple[int | None, FactRef | None]:
    """Days since the latest communication or call with the target, and a fact it holds.

    A record with no fact to cite is passed over: a figure on screen needs a source.
    """
    records: list[tuple[date, int]] = []
    if contact_id is not None:
        for source in session.scalars(
            select(Source).where(
                Source.matter_id == matter_id,
                Source.clio_type == SourceType.COMMUNICATION,
            )
        ):
            raw = source.raw_json or {}
            people = [*(raw.get("senders") or []), *(raw.get("receivers") or [])]
            if any(
                str(p.get("id")) == str(contact_id)
                for p in people
                if isinstance(p, dict)
            ):
                day = RawCommunication.model_validate(raw).date or (
                    source.clio_created_at.date() if source.clio_created_at else None
                )
                if day is not None:
                    records.append((day, source.id))
    for call in session.scalars(
        select(Call).where(Call.matter_id == matter_id, Call.source_id.is_not(None))
    ):
        if (
            call.target_json.get("target_id") == target_id
            and call.source_id is not None
        ):
            records.append((call.started_at.date(), call.source_id))
    for day, source_id in sorted(records, reverse=True):
        fact = session.scalars(
            renderable_facts(matter_id)
            .where(Fact.source_id == source_id)
            .order_by(Fact.significance.desc(), Fact.id)
        ).first()
        if fact is not None:
            return max((today - day).days, 0), fact_ref(fact)
    return None, None


def _id_after(target_id: str, prefix: str) -> int:
    try:
        return int(target_id.removeprefix(prefix))
    except ValueError as error:
        raise UnknownTarget(f"unknown target {target_id!r}") from error
