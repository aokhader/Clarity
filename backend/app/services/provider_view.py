"""Everything a provider receives, assembled only from `visible_facts_for_share`.

The firm's preview and the provider's own link both call `provider_payload`, so the
preview cannot drift from what the provider gets. Case-level sections carry labels
written here or by the pipeline as neutral wording (`status_change.label`), never a
case-level fact's title, which may paraphrase an internal note. A provider may open
only the cited document page of their own bill or record.
"""

from collections import defaultdict
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Fact, FactKind, Share, Source, SourceType
from app.schemas import (
    BillPayload,
    CaseStage,
    CaseStagePayload,
    CoveragePayload,
    PolicyLimitPayload,
    ProviderBillsTotalOut,
    ProviderCoverageOut,
    ProviderItemKind,
    ProviderItemOut,
    ProviderPayload,
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
from app.services.draft_check import check_text
from app.services.providers import distinct_requests
from app.services.share_values import shown_values, withheld_values
from app.services.visibility import (
    released_facts,
    share_is_live,
    visible_facts_for_share,
)

_ENDED_STAGES = {CaseStage.SETTLED, CaseStage.CLOSED}
# D35: a bills-and-liens item names its kind, read only from the two kinds that
# setting releases. Any other kind gets no name, so an internal fact never lends one.
ITEM_KIND_BY_FACT_KIND: dict[FactKind, ProviderItemKind] = {
    FactKind.MEDICAL_BILL: "bill",
    FactKind.LIEN: "lien",
}
# The only limits a link releases are the defendant's liability limits (D37).
_LIMIT_LABELS: dict[str | None, str] = {
    "person": "Liability limit per person",
    "occurrence": "Liability limit per occurrence",
    None: "Liability limit",
}
_LIMIT_ORDER = list(_LIMIT_LABELS)


class ShareGone(Exception):
    """The share is expired or revoked: the provider gets a plain message and no data."""


def _chronological(facts: list[Fact]) -> list[Fact]:
    return sorted(facts, key=lambda f: (f.event_date or date.min, f.id))


def _latest(facts: list[Fact]) -> Fact | None:
    return max(
        facts,
        key=lambda f: (f.event_date or date.min, f.significance, f.id),
        default=None,
    )


def has_cited_page(fact: Fact) -> bool:
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
        last_movement_on=_last_movement(facts, current),
    )


def _last_movement(facts: list[Fact], current: CaseStage | None) -> date | None:
    """When the case last moved, from the case events this link shows, or None.

    A dated move into the current stage answers it. Failing that, the latest dated
    event answers it only when every status change is dated: an undated change may be
    the latest, and dating the case from an older event would say nothing has happened
    since (critic Pass 2, finding 4).
    """
    events = [f for f in facts if _is_case_event(f)]
    into_current = [
        f.event_date for f in events if f.event_date and _stage_of(f) == current
    ]
    if current is not None and into_current:
        return max(into_current)
    changes = [f for f in events if f.kind is FactKind.STATUS_CHANGE]
    if any(f.event_date is None for f in changes):
        return None
    return max((f.event_date for f in events if f.event_date), default=None)


def _stage_of(fact: Fact) -> CaseStage | None:
    """The stage a case event moved the case to, when it says."""
    if fact.kind is FactKind.STATUS_CHANGE:
        return StatusChangePayload.model_validate(fact.value_json).to_stage
    return CaseStagePayload.model_validate(fact.value_json).stage


def _is_case_event(fact: Fact) -> bool:
    """A stage mapped from Clio's matter record is dated by the record's last edit,
    which is not something that happened in the case."""
    return not (
        fact.kind is FactKind.CASE_STAGE and fact.source.clio_type is SourceType.MATTER
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
        limits = _limits(by_setting["coverage_limits"])
    return ProviderCoverageOut(confirmed=confirmed, limits=limits)


def _limits(facts: list[Fact]) -> list[ProviderItemOut]:
    """The defendant's liability limits, the only ones a link releases (D37), each once
    and labelled by its basis, per person first.

    A limit several records restate is one line, citing its first statement. A limit
    with no basis is listed only when none states one: beside limits that do, it is a
    restatement, or a stray figure the firm's Coverage tile warns about.
    """
    stated = [
        (fact, PolicyLimitPayload.model_validate(fact.value_json))
        for fact in _chronological(facts)
    ]
    based = any(payload.per for _, payload in stated)
    stated.sort(key=lambda s: _LIMIT_ORDER.index(s[1].per))  # stable: dates kept
    limits = []
    listed: set[tuple[int | None, str | None]] = set()
    for fact, payload in stated:
        limit = (payload.amount_cents, payload.per)
        if limit in listed or (based and payload.per is None):
            continue
        listed.add(limit)
        limits.append(
            ProviderItemOut(
                fact_id=fact.id,
                on=fact.event_date,
                label=_LIMIT_LABELS[payload.per],
                amount_cents=payload.amount_cents,
                has_source=False,
            )
        )
    return limits


def _own_item(
    fact: Fact,
    *,
    amount_cents: int | None = None,
    has_source: bool = False,
    kind: ProviderItemKind | None = None,
) -> ProviderItemOut:
    """A bill, record, or request concerning the share's own provider, so its title may show."""
    return ProviderItemOut(
        fact_id=fact.id,
        on=fact.event_date,
        label=fact.title,
        amount_cents=amount_cents,
        has_source=has_source,
        kind=kind,
    )


def _requests(asks: list[Fact], received: list[Fact]) -> list[ProviderItemOut]:
    """What the firm still needs. Only records this link releases can answer a request,
    so the payload is still built from visible facts alone."""
    return [_own_item(f) for f in _chronological(distinct_requests([*asks, *received]))]


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
            has_source=has_cited_page(f),
            kind=ITEM_KIND_BY_FACT_KIND.get(f.kind),
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
    return [_own_item(f, has_source=has_cited_page(f)) for f in _chronological(facts)]


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
    payload = ProviderPayload(
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
        requests=_requests(by_setting["requests"], by_setting["own_records"])
        if settings.requests
        else None,
        bills=_bills(by_setting["own_bills"]) if settings.own_bills else None,
        bills_total=_bills_total(by_setting["own_bills"])
        if settings.own_bills
        else None,
        records=_records(by_setting["own_records"]) if settings.own_records else None,
        treatment_activity=_treatment(by_setting["treatment_activity"])
        if settings.treatment_activity
        else None,
    )
    released = {f.id: f for facts in by_setting.values() for f in facts}
    if payload.note and _note_locked(session, share, payload, released, now):
        # Rule 4: a note that states what this link withholds is never served, even
        # on a share stored before the note was checked (D25).
        payload = payload.model_copy(update={"note": None})
    return payload


def visible_by_id(session: Session, share: Share, now: datetime) -> dict[int, Fact]:
    """The facts the link releases, by id."""
    return {r.fact.id: r.fact for r in visible_facts_for_share(session, share, now)}


def _note_locked(
    session: Session,
    share: Share,
    payload: ProviderPayload,
    released: dict[int, Fact],
    now: datetime,
) -> bool:
    checked = check_text(
        payload.note or "",
        shown_values(payload, released),
        withheld_values(session, share, now),
    )
    return checked.verdict == "do_not_send"


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
