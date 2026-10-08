"""The provider boundary: which facts a share releases to a medical provider.

Every provider response is assembled from `visible_facts_for_share` and nothing else
(the rules are in docs/architecture.md under Visibility). The rule is default-deny. A
fact is released only when all of these hold:

- an enabled setting names its kind,
- the fact concerns the share's own provider, where the setting requires it,
- a policy limit is the defendant's liability limit (D37),
- the fact is tagged shareable and not flagged as mentioning strategy,
- the firm has not hidden it,
- the share is neither expired nor revoked.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Fact, FactKind, Share, Visibility
from app.schemas import ShareSetting, ShareSettings
from app.services.fact_views import renderable_facts

# The only kinds a share can ever release, and the setting that releases each. Case
# value, liability, negotiations, expenses, client contact, and every other kind are
# absent, so no setting can release them.
KINDS_BY_SETTING: dict[ShareSetting, frozenset[FactKind]] = {
    "case_stage": frozenset({FactKind.CASE_STAGE, FactKind.STATUS_CHANGE}),
    "coverage_exists": frozenset({FactKind.COVERAGE}),
    "coverage_limits": frozenset({FactKind.POLICY_LIMIT}),
    "own_bills": frozenset({FactKind.MEDICAL_BILL, FactKind.LIEN}),
    "own_records": frozenset({FactKind.RECORDS_RECEIVED}),
    "requests": frozenset({FactKind.RECORD_REQUEST, FactKind.TASK}),
    "treatment_activity": frozenset({FactKind.TREATMENT_VISIT}),
}

SETTING_BY_KIND: dict[FactKind, ShareSetting] = {
    kind: setting for setting, kinds in KINDS_BY_SETTING.items() for kind in kinds
}

# These settings release only facts about the share's own provider.
PROVIDER_SCOPED_SETTINGS: frozenset[ShareSetting] = frozenset(
    {"own_bills", "own_records", "requests"}
)

# A provider may open the cited page of these facts. Case-level facts show no source,
# because the source may be an internal note.
SOURCE_SETTINGS: frozenset[ShareSetting] = frozenset({"own_bills", "own_records"})


@dataclass(frozen=True)
class ReleasedFact:
    fact: Fact
    setting: ShareSetting


def fact_visibility(kind: FactKind, mentions_strategy: bool) -> Visibility:
    """The visibility tag to store on a new fact. The pipeline calls this; no model decides it."""
    if kind in SETTING_BY_KIND and not mentions_strategy:
        return Visibility.SHAREABLE
    return Visibility.INTERNAL


def share_is_live(share: Share, now: datetime) -> bool:
    if share.revoked_at is not None:
        return False
    return share.expires_at is None or now < share.expires_at


def _enabled_settings(share: Share) -> list[ShareSetting]:
    settings = ShareSettings.model_validate(share.settings_json)
    return [setting for setting in KINDS_BY_SETTING if getattr(settings, setting)]


def is_shared_limit(fact: Fact) -> bool:
    """Whether a policy limit may reach a provider: only the defendant's liability limit,
    the policy a lien is paid from (D37). The client's own policies are the client's
    business, and a limit whose policy the file does not name may be one of them."""
    return fact.value_json.get("policy") == "defendant_liability"


def _releases(fact: Fact, setting: ShareSetting, provider_contact_id: int) -> bool:
    if setting in PROVIDER_SCOPED_SETTINGS and (
        fact.provider_contact_id is None
        or fact.provider_contact_id != provider_contact_id
    ):
        return False
    if setting == "requests":
        # Only what the firm still needs; a fulfilled request or a completed task is history.
        return fact.value_json.get("status") == "open"
    if setting == "coverage_limits":
        return is_shared_limit(fact)
    return True


def released_facts(session: Session, share: Share) -> list[ReleasedFact]:
    """Facts the share's settings release, before the firm's per-item hiding.

    The share composer lists these so a hidden item can be shown again. A provider
    response must never be built from this list: use `visible_facts_for_share`.
    """
    kinds = {kind for s in _enabled_settings(share) for kind in KINDS_BY_SETTING[s]}
    if not kinds:
        return []
    facts = session.scalars(
        renderable_facts(share.matter_id)
        .where(
            Fact.kind.in_(kinds),
            Fact.visibility == Visibility.SHAREABLE,
            Fact.mentions_strategy.is_(False),
        )
        .order_by(Fact.event_date, Fact.id)
    )
    released = []
    for fact in facts:
        setting = SETTING_BY_KIND[fact.kind]
        if _releases(fact, setting, share.provider_contact_id):
            released.append(ReleasedFact(fact=fact, setting=setting))
    return released


def visible_facts_for_share(
    session: Session, share: Share, now: datetime
) -> list[ReleasedFact]:
    """Every fact the provider holding this share may see. The security boundary."""
    if not share_is_live(share, now):
        return []
    hidden = set(share.hidden_fact_ids_json or [])
    return [r for r in released_facts(session, share) if r.fact.id not in hidden]
