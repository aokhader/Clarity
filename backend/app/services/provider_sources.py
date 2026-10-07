"""What a provider may open behind a fact: one cited document page of their own bill
or record, and nothing else. Case-level facts show no source, since the source may
be an internal note (docs/architecture.md, Visibility)."""

from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Fact, Page, Share
from app.schemas import PageRef, ProviderSourceOut
from app.services import shares
from app.services.provider_view import ShareGone, has_cited_page
from app.services.source_views import page_image_path
from app.services.visibility import (
    SOURCE_SETTINGS,
    share_is_live,
    visible_facts_for_share,
)


class NotVisible(LookupError):
    """The share does not release this fact or page."""


def _sourced_facts(session: Session, share: Share, now: datetime) -> list[Fact]:
    """Visible own bills and records that cite a document page the provider may open."""
    if not share_is_live(share, now):
        raise ShareGone(f"share {share.id} is expired or revoked")
    return [
        r.fact
        for r in visible_facts_for_share(session, share, now)
        if r.setting in SOURCE_SETTINGS and has_cited_page(r.fact)
    ]


def provider_source(
    session: Session, token: str, fact_id: int, now: datetime
) -> ProviderSourceOut:
    share = shares.share_for_token(session, token)
    fact = next(
        (f for f in _sourced_facts(session, share, now) if f.id == fact_id), None
    )
    if fact is None:
        raise NotVisible(f"fact {fact_id} has no source this link can open")
    page = session.scalars(
        select(Page).where(
            Page.source_id == fact.source_id,
            Page.page_no == fact.page_no,
            Page.image_path.is_not(None),
        )
    ).first()
    page_ref = None
    if page is not None:
        page_ref = PageRef(
            page_id=page.id,
            page_no=page.page_no,
            image_url=f"/api/p/{token}/pages/{page.id}/image",
        )
    return ProviderSourceOut(
        fact_id=fact.id, title=fact.title, quote=fact.quote, page=page_ref
    )


def provider_page_image(
    session: Session, token: str, page_id: int, now: datetime
) -> Path:
    """The image of a page only if it is the cited page of a visible own bill or record."""
    share = shares.share_for_token(session, token)
    cited = {(f.source_id, f.page_no) for f in _sourced_facts(session, share, now)}
    page = session.get(Page, page_id)
    if page is None or (page.source_id, page.page_no) not in cited:
        raise NotVisible(f"page {page_id} is not open to this link")
    return page_image_path(session, page_id)
