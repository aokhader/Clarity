"""What a provider's link shows, and what the file withholds from it, as values to check.

`shown_values` walks the payload the link serves (`provider_payload`), so "supported"
means the provider already sees that figure or date. `withheld_values` is every amount
and date in the file, each with the rule that keeps it off this link. The matcher
tries shown values first, so a withheld value only decides a mention the link does not
support. A withheld value's reason names the rule that keeps it off the link.
"""

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models import Fact, FactKind, Share, Visibility
from app.schemas import (
    ExpensePayload,
    ProviderItemOut,
    ProviderPayload,
    ShareSetting,
    ShareSettings,
)
from app.services.bills import count_bills
from app.services.fact_views import renderable_facts
from app.services.known_values import KnownValue, fact_values
from app.services.text_mentions import DatePrecision, find_amounts, find_dates
from app.services.visibility import (
    PROVIDER_SCOPED_SETTINGS,
    SETTING_BY_KIND,
)

_SETTING_WORDS: dict[ShareSetting, str] = {
    "case_stage": "the case stage",
    "coverage_exists": "coverage",
    "coverage_limits": "policy limits",
    "own_bills": "bills",
    "own_records": "records",
    "requests": "requests",
    "treatment_activity": "treatment activity",
}
_PER_CUES = ("per person", "per occurrence")
_STAGE_KINDS = {FactKind.CASE_STAGE, FactKind.STATUS_CHANGE}
_NEVER_SHARED = "Kept internal: never shared with providers"
_OTHER_PROVIDER = "Kept internal: about another provider"
# The rank of a fact the link releases but whose value it does not display.
_RELEASED = 4


def shown_values(
    payload: ProviderPayload, visible: dict[int, Fact]
) -> list[KnownValue]:
    """Every amount and date on the link, read from the payload it serves.

    `visible` maps the ids of the facts the link releases to those facts, so each
    value can cite them.
    """
    limits = payload.coverage.limits if payload.coverage else None
    values: list[KnownValue] = []
    for items, what, cues in (
        (payload.bills, "a bill on this link", ()),
        (payload.requests, "a request on this link", ()),
        (payload.records, "a record on this link", ()),
        (limits, "a policy limit on this link", ("limit",)),
    ):
        for item in items or []:
            values += _item_values(item, what, cues, visible)
    values += _bill_totals(payload, visible)
    values += _case_dates(payload, visible)
    values += _link_dates(payload, visible)
    return values


def withheld_values(session: Session, share: Share, now: datetime) -> list[KnownValue]:
    """Every amount and date in the file, with the reason this link does not carry it."""
    settings = ShareSettings.model_validate(share.settings_json)
    hidden = set(share.hidden_fact_ids_json or [])
    facts = list(session.scalars(renderable_facts(share.matter_id)))
    values: list[KnownValue] = []
    for fact in facts:
        reason, rank = _withheld_because(fact, share, settings, hidden)
        values += fact_values(fact, reason, rank, exact_only=rank == _RELEASED)
    return values + _internal_totals(facts)


def _internal_totals(facts: list[Fact]) -> list[KnownValue]:
    """Figures the firm page computes from internal facts and no single fact holds:
    the Firm spend total, and the bills of every provider together (D25)."""
    totals = []
    spent = [
        (f, cents)
        for f in facts
        if f.kind is FactKind.EXPENSE
        and (cents := ExpensePayload.model_validate(f.value_json).amount_cents)
    ]
    if spent:
        totals.append(
            KnownValue(
                _NEVER_SHARED,
                amount_cents=sum(cents for _, cents in spent),
                facts=tuple(f for f, _ in spent),
            )
        )
    counted = count_bills([f for f in facts if f.kind is FactKind.MEDICAL_BILL])
    if len(counted) > 1:
        totals.append(
            KnownValue(
                _OTHER_PROVIDER,
                amount_cents=sum(c.total_cents for c in counted),
                facts=tuple(f for c in counted for f in c.facts),
                rank=1,
            )
        )
    return totals


def _withheld_because(
    fact: Fact, share: Share, settings: ShareSettings, hidden: set[int]
) -> tuple[str, int]:
    """The visibility rule that keeps this fact's values off the link, most severe first."""
    setting = SETTING_BY_KIND.get(fact.kind)
    if (
        setting is None
        or fact.visibility is Visibility.INTERNAL
        or fact.mentions_strategy
    ):
        return _NEVER_SHARED, 0
    if (
        setting in PROVIDER_SCOPED_SETTINGS
        and fact.provider_contact_id != share.provider_contact_id
    ):
        return _OTHER_PROVIDER, 1
    if fact.id in hidden:
        return "Hidden from this link by the firm", 2
    if not getattr(settings, setting):
        return f"This link does not share {_SETTING_WORDS[setting]}", 3
    # A released fact whose value the link does not display: a balance, a second read,
    # a day behind a month, or a stage date other than the latest.
    return "Not shown on this link", _RELEASED


def _facts(ids: list[int], visible: dict[int, Fact]) -> tuple[Fact, ...]:
    return tuple(visible[i] for i in ids if i in visible)


def _item_values(
    item: ProviderItemOut,
    what: str,
    cues: tuple[str, ...],
    visible: dict[int, Fact],
) -> list[KnownValue]:
    facts = _facts([item.fact_id], visible)
    label = item.label.lower()
    subject = (label, *cues, *(c for c in _PER_CUES if c in label))
    values = _restated(item.label, what, facts)
    if item.amount_cents is not None:
        values.append(
            KnownValue(what, amount_cents=item.amount_cents, facts=facts, cues=subject)
        )
    if item.on is not None:
        values.append(KnownValue(what, on=item.on, facts=facts, cues=(label,)))
    return values


def _restated(label: str, what: str, facts: tuple[Fact, ...]) -> list[KnownValue]:
    """Amounts and dates a label itself states, since the link shows the label."""
    values = [
        KnownValue(what, amount_cents=m.cents, facts=facts) for m in find_amounts(label)
    ]
    for mention in find_dates(label):
        if mention.precision is not DatePrecision.MONTH_DAY:
            month_only = mention.precision is DatePrecision.MONTH
            values.append(
                KnownValue(what, on=mention.on, month_only=month_only, facts=facts)
            )
    return values


def _bill_totals(
    payload: ProviderPayload, visible: dict[int, Fact]
) -> list[KnownValue]:
    bills = payload.bills or []
    values = []
    if payload.bills_total is not None:
        counted = [
            i.fact_id
            for i in bills
            if i.fact_id in visible and visible[i.fact_id].kind is FactKind.MEDICAL_BILL
        ]
        values.append(
            KnownValue(
                "the bills total on this link",
                amount_cents=payload.bills_total.amount_cents,
                facts=_facts(counted, visible),
                cues=("total", "bill"),
            )
        )
    listed = sum(i.amount_cents or 0 for i in bills)
    total = payload.bills_total.amount_cents if payload.bills_total else None
    if listed and listed != total:
        # The generated update adds every listed item, liens included, while the bills
        # total counts bills only. Both figures are on the link, so both are supported.
        values.append(
            KnownValue(
                "the sum of the items listed under bills on this link",
                amount_cents=listed,
                facts=_facts([i.fact_id for i in bills], visible),
            )
        )
    return values


def _case_dates(payload: ProviderPayload, visible: dict[int, Fact]) -> list[KnownValue]:
    stage_facts = [f for f in visible.values() if f.kind in _STAGE_KINDS]
    values = []
    if payload.status and payload.status.last_movement_on:
        on = payload.status.last_movement_on
        values.append(
            KnownValue(
                "the case's last movement on this link",
                on=on,
                facts=tuple(f for f in stage_facts if f.event_date == on),
                cues=("last movement", "moved"),
            )
        )
    for update in payload.updates or []:
        facts = tuple(
            f
            for f in stage_facts
            if f.kind is FactKind.STATUS_CHANGE and f.event_date == update.on
        )
        values += _restated(update.label, "a case update on this link", facts)
        if update.on is not None:
            values.append(
                KnownValue(
                    "a case update on this link",
                    on=update.on,
                    facts=facts,
                    cues=(update.label.lower(),),
                )
            )
    return values


def _link_dates(payload: ProviderPayload, visible: dict[int, Fact]) -> list[KnownValue]:
    values = [
        KnownValue(
            "the date this link was shared", on=payload.shared_on, cues=("shared",)
        )
    ]
    if payload.expires_on is not None:
        values.append(
            KnownValue(
                "the date this link expires",
                on=payload.expires_on,
                cues=("expire", "stops working"),
            )
        )
    if payload.treatment_activity is not None:
        month = date.fromisoformat(f"{payload.treatment_activity.last_visit_month}-01")
        visits = tuple(
            f
            for f in visible.values()
            if f.kind is FactKind.TREATMENT_VISIT
            and f.event_date is not None
            and (f.event_date.year, f.event_date.month) == (month.year, month.month)
        )
        values.append(
            KnownValue(
                "the month of the latest visit on this link",
                on=month,
                month_only=True,
                facts=visits,
            )
        )
    return values
