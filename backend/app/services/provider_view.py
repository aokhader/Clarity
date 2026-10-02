"""Everything a provider receives, assembled only from `visible_facts_for_share`.

The firm's preview and the provider's own link both call `provider_payload`, so the
preview cannot drift from what the provider gets. Case-level sections carry labels
written here or by the pipeline as neutral wording (`status_change.label`), never a
case-level fact's title, which may paraphrase an internal note. A provider may open
only the cited document page of their own bill or record.
"""

from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Fact, FactKind, Page, Share, Source, SourceType
from app.schemas import (
    BillPayload,
    CaseStage,
    CaseStagePayload,
    CoveragePayload,
    PageRef,
    PolicyLimitPayload,
    ProviderBillsTotalOut,
    ProviderCoverageOut,
    ProviderItemOut,
    ProviderPayload,
    ProviderSourceOut,
    ProviderStatusOut,
    ProviderTreatmentOut,
    ProviderUpdateOut,
    ShareItemOut,
    SharePreviewOut,
    ShareSetting,
    ShareSettings,
    StatusChangePayload,
)
from app.services import shares
from app.services.bills import CountedBills, count_bills
from app.services.clio_records import RawMatter
from app.services.providers import distinct_requests
from app.services.source_views import page_image_path
from app.services.visibility import (
    SOURCE_SETTINGS,
    released_facts,
    share_is_live,
    visible_facts_for_share,
)

_ENDED_STAGES = {CaseStage.SETTLED, CaseStage.CLOSED}
_LIMIT_LABELS = {
    "person": "Policy limit per person",
    "occurrence": "Policy limit per occurrence",
}


class ShareGone(Exception):
    """The share is expired or revoked: the provider gets a plain message and no data."""


class NotVisible(LookupError):
    """The share does not release this fact or page."""


def _chronological(facts: list[Fact]) -> list[Fact]:
    return sorted(facts, key=lambda f: (f.event_date or date.min, f.id))


def _latest(facts: list[Fact]) -> Fact | None:
    return max(
        facts,
        key=lambda f: (f.event_date or date.min, f.significance, f.id),
        default=None,
    )


def _has_cited_page(fact: Fact) -> bool:
    return fact.source.clio_type is SourceType.DOCUMENT and fact.page_no is not None


def _matter(session: Session, matter_id: int) -> RawMatter | None:
    source = session.scalars(
        select(Source).where(
            Source.matter_id == matter_id, Source.clio_type == SourceType.MATTER
        )
    ).first()
    return RawMatter.model_validate(source.raw_json) if source else None


def _status(facts: list[Fact], matter: RawMatter | None) -> ProviderStatusOut:
    current: CaseStage | None = None
    if stage_fact := _latest([f for f in facts if f.kind is FactKind.CASE_STAGE]):
        current = CaseStagePayload.model_validate(stage_fact.value_json).stage
    change = _latest([f for f in facts if f.kind is FactKind.STATUS_CHANGE])
    if current is None and change is not None:
        current = StatusChangePayload.model_validate(change.value_json).to_stage
    if matter and matter.status:
        active = matter.status.lower() != "closed"
    else:
        active = current not in _ENDED_STAGES
    return ProviderStatusOut(
        stages=list(CaseStage),
        current=current,
        active=active,
        last_movement_on=max(
            (f.event_date for f in facts if f.event_date), default=None
        ),
    )


def _updates(facts: list[Fact]) -> list[ProviderUpdateOut]:
    changes = [f for f in facts if f.kind is FactKind.STATUS_CHANGE]
    return [
        ProviderUpdateOut(
            on=f.event_date,
            label=StatusChangePayload.model_validate(f.value_json).label,
        )
        for f in reversed(_chronological(changes))
    ]


def _coverage(
    by_setting: dict[ShareSetting, list[Fact]], settings: ShareSettings
) -> ProviderCoverageOut | None:
    if not (settings.coverage_exists or settings.coverage_limits):
        return None
    confirmed = None
    if settings.coverage_exists:
        confirmed = any(
            CoveragePayload.model_validate(f.value_json).confirmed is True
            for f in by_setting["coverage_exists"]
        )
    limits = None
    if settings.coverage_limits:
        limits = []
        for fact in _chronological(by_setting["coverage_limits"]):
            payload = PolicyLimitPayload.model_validate(fact.value_json)
            limits.append(
                ProviderItemOut(
                    fact_id=fact.id,
                    on=fact.event_date,
                    label=_LIMIT_LABELS.get(payload.per or "", "Policy limit"),
                    amount_cents=payload.amount_cents,
                    has_source=False,
                )
            )
    return ProviderCoverageOut(confirmed=confirmed, limits=limits)


def _own_item(
    fact: Fact, *, amount_cents: int | None = None, has_source: bool = False
) -> ProviderItemOut:
    """A bill, record, or request concerning the share's own provider, so its title may show."""
    return ProviderItemOut(
        fact_id=fact.id,
        on=fact.event_date,
        label=fact.title,
        amount_cents=amount_cents,
        has_source=has_source,
    )


def _requests(facts: list[Fact]) -> list[ProviderItemOut]:
    return [_own_item(f) for f in _chronological(distinct_requests(facts))]


def _counted_bills(facts: list[Fact]) -> CountedBills | None:
    """The share's own bills with each charge once, from the record `count_bills` picks."""
    counted = count_bills(facts)
    return counted[0] if counted else None


def _bills(facts: list[Fact]) -> list[ProviderItemOut]:
    """Liens, and the bills of the counted record; restatements of the same charges are left out."""
    counted = _counted_bills(facts)
    listed = [f for f in facts if f.kind is not FactKind.MEDICAL_BILL]
    listed += counted.facts if counted else []
    return [
        _own_item(
            f,
            amount_cents=BillPayload.model_validate(f.value_json).amount_cents,
            has_source=_has_cited_page(f),
        )
        for f in _chronological(listed)
    ]


def _bills_total(facts: list[Fact]) -> ProviderBillsTotalOut | None:
    counted = _counted_bills(facts)
    if counted is None:
        return None
    return ProviderBillsTotalOut(
        amount_cents=counted.total_cents, bill_count=len(counted.facts)
    )


def _records(facts: list[Fact]) -> list[ProviderItemOut]:
    return [_own_item(f, has_source=_has_cited_page(f)) for f in _chronological(facts)]


def _treatment(facts: list[Fact]) -> ProviderTreatmentOut | None:
    last_visit = max((f.event_date for f in facts if f.event_date), default=None)
    if last_visit is None:
        return None
    return ProviderTreatmentOut(last_visit_month=last_visit.strftime("%Y-%m"))


def provider_payload(session: Session, share: Share, now: datetime) -> ProviderPayload:
    """What the provider holding this share receives. A section is None when its setting is off."""
    if not share_is_live(share, now):
        raise ShareGone(f"share {share.id} is expired or revoked")
    settings = ShareSettings.model_validate(share.settings_json)
    by_setting: dict[ShareSetting, list[Fact]] = defaultdict(list)
    for released in visible_facts_for_share(session, share, now):
        by_setting[released.setting].append(released.fact)
    matter = _matter(session, share.matter_id)
    stage_facts = by_setting["case_stage"]
    return ProviderPayload(
        provider_name=shares.contact_name(
            session, share.matter_id, share.provider_contact_id
        )
        or "Your office",
        patient_name=matter.client.name if matter and matter.client else None,
        firm_name=None,
        shared_on=share.created_at.date(),
        expires_on=share.expires_at.date() if share.expires_at else None,
        note=share.note,
        status=_status(stage_facts, matter) if settings.case_stage else None,
        updates=_updates(stage_facts) if settings.case_stage else None,
        coverage=_coverage(by_setting, settings),
        requests=_requests(by_setting["requests"]) if settings.requests else None,
        bills=_bills(by_setting["own_bills"]) if settings.own_bills else None,
        bills_total=_bills_total(by_setting["own_bills"])
        if settings.own_bills
        else None,
        records=_records(by_setting["own_records"]) if settings.own_records else None,
        treatment_activity=_treatment(by_setting["treatment_activity"])
        if settings.treatment_activity
        else None,
    )


def share_preview(session: Session, share: Share, now: datetime) -> SharePreviewOut:
    """The provider's payload exactly, plus every released item with its hide state."""
    payload = provider_payload(session, share, now)
    hidden = set(share.hidden_fact_ids_json or [])
    items = [
        ShareItemOut(
            fact_id=r.fact.id,
            setting=r.setting,
            title=r.fact.title,
            event_date=r.fact.event_date,
            hidden=r.fact.id in hidden,
        )
        for r in released_facts(session, share)
    ]
    return SharePreviewOut(payload=payload, items=items)


def open_link(session: Session, token: str, now: datetime) -> ProviderPayload:
    """The provider opening their link: the payload, and an opened event for the firm."""
    share = shares.share_for_token(session, token)
    payload = provider_payload(session, share, now)
    shares.record_opened(session, share, now)
    return payload


def _sourced_facts(session: Session, share: Share, now: datetime) -> list[Fact]:
    """Visible own bills and records that cite a document page the provider may open."""
    if not share_is_live(share, now):
        raise ShareGone(f"share {share.id} is expired or revoked")
    return [
        r.fact
        for r in visible_facts_for_share(session, share, now)
        if r.setting in SOURCE_SETTINGS and _has_cited_page(r.fact)
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
