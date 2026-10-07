"""The providers panel on the firm page: each medical provider's totals and share status.

This is a firm view, so it counts every fact about the provider, shareable or not.
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Fact, FactKind, Share, Source, SourceType
from app.schemas import ProviderOut, ShareStatusOut
from app.services import shares
from app.services.bills import count_bills
from app.services.clio_records import RawRelationship
from app.services.fact_views import renderable_facts
from app.services.record_requests import (
    open_record_requests,
    outstanding_record_requests,
)
from app.services.visibility import share_is_live


def distinct_requests(facts: list[Fact]) -> list[Fact]:
    """Outstanding record requests and open tasks, each ask listed once.

    A task that raised a request is the same ask, so it is left out even after the
    request is answered. `facts` must include the records received that can answer a
    request (`record_requests.py`).
    """
    raised_by = {f.source_id for f in open_record_requests(facts)}
    tasks = [
        f
        for f in facts
        if f.kind is FactKind.TASK
        and f.value_json.get("status") == "open"
        and f.source_id not in raised_by
    ]
    return outstanding_record_requests(facts) + tasks


def _billed_cents(facts: list[Fact]) -> int | None:
    """The provider's bills total, or None when no bill on file carries an amount."""
    counted = count_bills(facts)
    return sum(c.total_cents for c in counted) if counted else None


def _role_labels(session: Session, matter_id: int) -> dict[int, str]:
    """The relationship description each contact has on the matter, as written in Clio."""
    labels: dict[int, str] = {}
    for source in session.scalars(
        select(Source).where(
            Source.matter_id == matter_id,
            Source.clio_type == SourceType.RELATIONSHIP,
        )
    ):
        relationship = RawRelationship.model_validate(source.raw_json)
        contact = relationship.contact
        if contact and contact.id is not None and relationship.description:
            labels.setdefault(int(contact.id), relationship.description)
    return labels


def _current_share(provider_shares: list[Share], now: datetime) -> Share | None:
    """The newest live link, or else the newest link, so a withdrawn one still shows."""
    live = [s for s in provider_shares if share_is_live(s, now)]
    if live:
        return live[0]
    return provider_shares[0] if provider_shares else None


def providers_panel(
    session: Session, matter_id: int, now: datetime
) -> list[ProviderOut]:
    provider_ids = shares.medical_provider_ids(session, matter_id)
    if not provider_ids:
        return []
    facts_by_provider: dict[int, list[Fact]] = {pid: [] for pid in provider_ids}
    for fact in session.scalars(
        renderable_facts(matter_id).where(Fact.provider_contact_id.in_(provider_ids))
    ):
        if fact.provider_contact_id is not None:
            facts_by_provider[fact.provider_contact_id].append(fact)
    all_shares = shares.list_shares(session, matter_id)
    stats = shares.open_stats(session, [s.id for s in all_shares])
    labels = _role_labels(session, matter_id)

    rows = []
    for pid in provider_ids:
        facts = facts_by_provider[pid]
        share = _current_share(
            [s for s in all_shares if s.provider_contact_id == pid], now
        )
        status = None
        if share is not None:
            opened_count, last_opened_at = stats.get(share.id, (0, None))
            status = ShareStatusOut(
                share_id=share.id,
                created_at=share.created_at,
                expires_at=share.expires_at,
                revoked=share.revoked_at is not None,
                opened_count=opened_count,
                last_opened_at=last_opened_at,
            )
        rows.append(
            ProviderOut(
                contact_id=pid,
                name=shares.contact_name(session, matter_id, pid) or f"Contact {pid}",
                role_label=labels.get(pid),
                billed_cents=_billed_cents(facts),
                records_received=sum(
                    1 for f in facts if f.kind is FactKind.RECORDS_RECEIVED
                ),
                open_requests=len(distinct_requests(facts)),
                share=status,
            )
        )
    return sorted(rows, key=lambda row: row.name.lower())
