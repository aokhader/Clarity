"""Share records: create, list, update, and revoke a provider's link.

What a share releases is decided in `services/visibility.py`, and the provider's
response is assembled in `services/provider_view.py`. This module only manages the
records and the open events.
"""

import secrets
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Digest,
    DigestKind,
    Share,
    ShareEvent,
    ShareEventType,
    Source,
    SourceType,
    User,
)
from app.schemas import (
    ContactRole,
    FieldMappingContent,
    ShareCreate,
    ShareOut,
    ShareSettings,
    ShareUpdate,
)
from app.services.clio_records import RawContact

# docs/architecture.md: provider tokens carry at least 32 bytes of randomness.
TOKEN_BYTES = 32


class ShareNotFound(LookupError):
    pass


class UnknownUser(LookupError):
    pass


class NotAProvider(ValueError):
    pass


class ShareRevoked(ValueError):
    pass


class InvalidShareUpdate(ValueError):
    pass


def medical_provider_ids(session: Session, matter_id: int) -> set[int]:
    """Contacts the merge step classified as medical providers on this matter."""
    stored = session.scalars(
        select(Digest)
        .where(Digest.matter_id == matter_id, Digest.kind == DigestKind.FIELD_MAPPING)
        .order_by(Digest.created_at.desc(), Digest.id.desc())
    ).first()
    if stored is None:
        return set()
    mapping = FieldMappingContent.model_validate(stored.content_json)
    return {
        contact_id
        for contact_id, role in mapping.contact_roles.items()
        if role is ContactRole.MEDICAL_PROVIDER
    }


def contact_name(session: Session, matter_id: int, contact_id: int) -> str | None:
    source = session.scalars(
        select(Source).where(
            Source.matter_id == matter_id,
            Source.clio_type == SourceType.CONTACT,
            Source.clio_id == str(contact_id),
        )
    ).first()
    return RawContact.model_validate(source.raw_json).name if source else None


def require_user(session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise UnknownUser(f"user {user_id} does not exist")
    return user


def share_url(share: Share) -> str:
    return f"{get_settings().frontend_origin}/p/{share.token}"


def draft_share(
    session: Session, matter_id: int, body: ShareCreate, now: datetime
) -> Share:
    """A share built from the request but not saved, so the composer can preview it.

    `create_share` saves exactly this, so the preview matches the link it creates.
    """
    if body.provider_contact_id not in medical_provider_ids(session, matter_id):
        raise NotAProvider(
            f"contact {body.provider_contact_id} is not a medical provider on matter {matter_id}"
        )
    days = body.expires_in_days or get_settings().share_default_expiry_days
    return Share(
        token=secrets.token_urlsafe(TOKEN_BYTES),
        matter_id=matter_id,
        provider_contact_id=body.provider_contact_id,
        settings_json=body.settings.model_dump(),
        hidden_fact_ids_json=sorted(set(body.hidden_fact_ids)),
        note=body.note,
        created_at=now,
        expires_at=now + timedelta(days=days),
    )


def save_share(session: Session, share: Share, user: User) -> Share:
    """Store a share built by `draft_share`, as created by `user`."""
    share.created_by = user.id
    session.add(share)
    session.commit()
    return share


def get_share(session: Session, share_id: int) -> Share:
    share = session.get(Share, share_id)
    if share is None:
        raise ShareNotFound(f"share {share_id} does not exist")
    return share


def share_for_token(session: Session, token: str) -> Share:
    share = session.scalars(select(Share).where(Share.token == token)).first()
    if share is None:
        raise ShareNotFound("no share has this link")
    return share


def list_shares(session: Session, matter_id: int) -> list[Share]:
    return list(
        session.scalars(
            select(Share)
            .where(Share.matter_id == matter_id)
            .order_by(Share.created_at.desc(), Share.id.desc())
        )
    )


def apply_update(share: Share, body: ShareUpdate) -> Share:
    """Change only the fields present in the request body; the caller commits."""
    if share.revoked_at is not None:
        raise ShareRevoked(f"share {share.id} is revoked; create a new one")
    fields = body.model_fields_set
    if "settings" in fields:
        share.settings_json = (body.settings or ShareSettings()).model_dump()
    if "hidden_fact_ids" in fields:
        share.hidden_fact_ids_json = sorted(set(body.hidden_fact_ids or []))
    if "note" in fields:
        share.note = body.note
    if "expires_at" in fields:
        if body.expires_at is not None and body.expires_at.tzinfo is None:
            raise InvalidShareUpdate("expires_at needs a time zone offset")
        share.expires_at = body.expires_at
    return share


def revoke_share(session: Session, share: Share, now: datetime) -> Share:
    if share.revoked_at is None:
        share.revoked_at = now
        session.commit()
    return share


def record_opened(session: Session, share: Share, now: datetime) -> None:
    session.add(
        ShareEvent(share_id=share.id, event=ShareEventType.OPENED, created_at=now)
    )
    session.commit()


def open_stats(
    session: Session, share_ids: list[int]
) -> dict[int, tuple[int, datetime | None]]:
    """Open count and last open time per share."""
    rows = session.execute(
        select(
            ShareEvent.share_id,
            func.count(ShareEvent.id),
            func.max(ShareEvent.created_at),
        )
        .where(
            ShareEvent.share_id.in_(share_ids),
            ShareEvent.event == ShareEventType.OPENED,
        )
        .group_by(ShareEvent.share_id)
    )
    return {share_id: (count, last) for share_id, count, last in rows}


def share_out(
    share: Share, provider_name: str, stats: tuple[int, datetime | None]
) -> ShareOut:
    opened_count, last_opened_at = stats
    return ShareOut(
        id=share.id,
        matter_id=share.matter_id,
        provider_contact_id=share.provider_contact_id,
        provider_name=provider_name,
        url=share_url(share),
        settings=ShareSettings.model_validate(share.settings_json),
        hidden_fact_ids=share.hidden_fact_ids_json,
        note=share.note,
        created_by=share.created_by,
        created_at=share.created_at,
        expires_at=share.expires_at,
        revoked_at=share.revoked_at,
        opened_count=opened_count,
        last_opened_at=last_opened_at,
    )


def shares_out(session: Session, shares: list[Share]) -> list[ShareOut]:
    stats = open_stats(session, [s.id for s in shares])
    return [
        share_out(
            share,
            contact_name(session, share.matter_id, share.provider_contact_id)
            or f"Contact {share.provider_contact_id}",
            stats.get(share.id, (0, None)),
        )
        for share in shares
    ]
