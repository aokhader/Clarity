"""The provider boundary. A failure here means a provider could see what the firm keeps."""

from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Confidence,
    Fact,
    FactKind,
    Origin,
    Share,
    Source,
    SourceType,
    Visibility,
)
from app.schemas import (
    ProviderItemOut,
    ProviderPayload,
    ShareSetting,
    ShareSettings,
    validate_payload,
)
from app.services.provider_view import ITEM_KIND_BY_FACT_KIND, provider_payload
from app.services.visibility import (
    KINDS_BY_SETTING,
    PROVIDER_SCOPED_SETTINGS,
    SETTING_BY_KIND,
    fact_visibility,
    visible_facts_for_share,
)
from tests.fixtures.synthetic_matter import MATTER_ID, ORTHO_ID, THERAPY_ID

NOW = datetime.now(UTC)
ALL_ON = ShareSettings.model_validate(dict.fromkeys(KINDS_BY_SETTING, True))
# Named in docs/architecture.md as never shareable under any setting.
NEVER_SHARED = {
    FactKind.CASE_VALUE,
    FactKind.LIABILITY,
    FactKind.DEMAND,
    FactKind.OFFER,
    FactKind.SETTLEMENT,
    FactKind.EXPENSE,
    FactKind.CLIENT_CONTACT,
}


def _share(
    *,
    provider: int = ORTHO_ID,
    settings: ShareSettings = ALL_ON,
    hidden: Iterable[int] = (),
    matter_id: int = MATTER_ID,
    expires_at: datetime | None = None,
    revoked_at: datetime | None = None,
) -> Share:
    return Share(
        token="test-token",
        matter_id=matter_id,
        provider_contact_id=provider,
        settings_json=settings.model_dump(),
        hidden_fact_ids_json=list(hidden),
        note=None,
        created_by=1,
        created_at=NOW - timedelta(days=1),
        expires_at=expires_at,
        revoked_at=revoked_at,
    )


def _visible(session: Session, share: Share) -> list[Fact]:
    return [r.fact for r in visible_facts_for_share(session, share, NOW)]


def _fact(session: Session, kind: FactKind, provider: int | None) -> Fact:
    fact = session.scalars(
        select(Fact).where(Fact.kind == kind, Fact.provider_contact_id == provider)
    ).first()
    assert fact is not None, f"the seed has no {kind} fact for provider {provider}"
    return fact


@pytest.mark.parametrize("provider", [ORTHO_ID, THERAPY_ID])
def test_internal_kinds_never_appear(seeded: Session, provider: int) -> None:
    # The seed holds every never-shared kind, so their absence below means something.
    assert NEVER_SHARED <= {fact.kind for fact in seeded.scalars(select(Fact))}

    visible = _visible(seeded, _share(provider=provider))

    assert visible
    for fact in visible:
        assert fact.kind in SETTING_BY_KIND
        assert fact.kind not in NEVER_SHARED
        assert fact.visibility is Visibility.SHAREABLE
        assert not fact.mentions_strategy


def test_no_setting_can_release_a_never_shared_kind() -> None:
    assert NEVER_SHARED.isdisjoint(SETTING_BY_KIND)


def test_strategy_flag_and_internal_tag_override_the_kind(seeded: Session) -> None:
    bill = _fact(seeded, FactKind.MEDICAL_BILL, ORTHO_ID)
    lien = _fact(seeded, FactKind.LIEN, ORTHO_ID)
    assert {bill, lien} <= set(_visible(seeded, _share()))

    bill.mentions_strategy = True
    lien.visibility = Visibility.INTERNAL
    seeded.flush()

    visible = _visible(seeded, _share())
    assert bill not in visible
    assert lien not in visible


@pytest.mark.parametrize(
    ("provider", "other"), [(ORTHO_ID, THERAPY_ID), (THERAPY_ID, ORTHO_ID)]
)
def test_another_providers_facts_never_appear(
    seeded: Session, provider: int, other: int
) -> None:
    others_bill = _fact(seeded, FactKind.MEDICAL_BILL, other)

    released = visible_facts_for_share(seeded, _share(provider=provider), NOW)

    assert others_bill not in [r.fact for r in released]
    scoped = [r.fact for r in released if r.setting in PROVIDER_SCOPED_SETTINGS]
    assert scoped
    # Unattributed facts are scoped out too: a bill with no provider is nobody's to see.
    assert all(fact.provider_contact_id == provider for fact in scoped)


@pytest.mark.parametrize("setting", list(KINDS_BY_SETTING))
def test_a_setting_turned_off_removes_its_facts(
    seeded: Session, setting: ShareSetting
) -> None:
    kinds = KINDS_BY_SETTING[setting]
    assert any(f.kind in kinds for f in _visible(seeded, _share()))

    off = ALL_ON.model_copy(update={setting: False})

    assert not any(f.kind in kinds for f in _visible(seeded, _share(settings=off)))


def test_default_settings_leave_limits_and_treatment_out(seeded: Session) -> None:
    kinds = {f.kind for f in _visible(seeded, _share(settings=ShareSettings()))}

    assert FactKind.POLICY_LIMIT not in kinds
    assert FactKind.TREATMENT_VISIT not in kinds
    assert {
        FactKind.CASE_STAGE,
        FactKind.MEDICAL_BILL,
        FactKind.RECORD_REQUEST,
    } <= kinds


def test_only_open_requests_are_released(seeded: Session) -> None:
    task = _fact(seeded, FactKind.TASK, ORTHO_ID)
    assert task in _visible(seeded, _share())

    task.value_json = task.value_json | {"status": "complete"}
    seeded.flush()

    assert task not in _visible(seeded, _share())


def test_hidden_facts_are_removed(seeded: Session) -> None:
    bill = _fact(seeded, FactKind.MEDICAL_BILL, ORTHO_ID)
    coverage = _fact(seeded, FactKind.COVERAGE, None)

    visible = _visible(seeded, _share(hidden=[bill.id, coverage.id]))

    assert visible
    assert bill not in visible
    assert coverage not in visible


@pytest.mark.parametrize(
    "dates",
    [
        {"expires_at": NOW - timedelta(seconds=1)},
        {"revoked_at": NOW - timedelta(hours=1)},
        {"expires_at": NOW + timedelta(days=30), "revoked_at": NOW},
    ],
    ids=["expired", "revoked", "revoked-before-expiry"],
)
def test_expired_and_revoked_shares_return_nothing(
    seeded: Session, dates: dict[str, datetime]
) -> None:
    assert _visible(seeded, _share(**dates)) == []


def test_a_share_inside_its_expiry_is_live(seeded: Session) -> None:
    assert _visible(seeded, _share(expires_at=NOW + timedelta(minutes=1)))


def test_another_matters_facts_never_appear(seeded: Session) -> None:
    assert _visible(seeded, _share(matter_id=MATTER_ID + 1)) == []


# --- D20, D21: economic damages, recovery caps, and whose policy a limit is ----------


def _new_fact(
    session: Session, kind: FactKind, value: dict[str, object], provider: int | None
) -> Fact:
    source = Source(
        matter_id=MATTER_ID,
        clio_type=SourceType.NOTE,
        clio_id=f"visibility-note-{session.query(Source).count()}",
        raw_json={},
    )
    session.add(source)
    session.flush()
    fact = Fact(
        matter_id=MATTER_ID,
        kind=kind,
        title="A figure",
        value_json=validate_payload(kind, value),
        source_id=source.id,
        quote="A figure",
        provider_contact_id=provider,
        # Tagged shareable on purpose: the kind alone must keep it in.
        visibility=Visibility.SHAREABLE,
        confidence=Confidence.HIGH,
        origin=Origin.MODEL,
    )
    session.add(fact)
    session.flush()
    return fact


@pytest.mark.parametrize("kind", [FactKind.ECONOMIC_DAMAGES, FactKind.RECOVERY_CAP])
def test_damages_and_caps_are_internal_by_default_deny(
    seeded: Session, kind: FactKind
) -> None:
    assert kind not in SETTING_BY_KIND
    assert fact_visibility(kind, mentions_strategy=False) is Visibility.INTERNAL

    fact = _new_fact(seeded, kind, {"amount_cents": 1_000_00, "basis": "x"}, ORTHO_ID)

    assert fact not in _visible(seeded, _share())


# D37: the client's own policies are the client's business, and a limit whose policy
# the file does not name may be one of them.
NOT_THE_DEFENDANTS = ["client_no_fault", "client_um_uim", "client_other", None]


def _limit(session: Session, policy: str | None, per: str | None = "person") -> Fact:
    value = {"amount_cents": 2_500_00, "per": per, "policy": policy}
    return _new_fact(session, FactKind.POLICY_LIMIT, value, None)


@pytest.mark.parametrize("policy", NOT_THE_DEFENDANTS)
def test_only_the_defendants_liability_limits_are_released(
    seeded: Session, policy: str | None
) -> None:
    theirs = _limit(seeded, policy)
    defendants = _limit(seeded, "defendant_liability")
    limits_off = ALL_ON.model_copy(update={"coverage_limits": False})

    visible = _visible(seeded, _share())

    assert defendants in visible
    assert theirs not in visible
    assert defendants not in _visible(seeded, _share(settings=limits_off))


@pytest.mark.parametrize("provider", [ORTHO_ID, THERAPY_ID])
def test_a_providers_page_never_lists_a_client_policy_or_an_untagged_limit(
    seeded: Session, provider: int
) -> None:
    others = [
        _limit(seeded, policy, per)
        for policy in NOT_THE_DEFENDANTS
        for per in ("person", "occurrence", None)
    ]

    payload = provider_payload(seeded, _share(provider=provider), NOW)

    assert payload.coverage is not None and payload.coverage.limits
    listed = {item.fact_id for item in payload.coverage.limits}
    assert listed.isdisjoint(fact.id for fact in others)
    for fact_id in listed:
        assert seeded.get_one(Fact, fact_id).value_json["policy"] == (
            "defendant_liability"
        )
    assert 2_500_00 not in {item.amount_cents for item in payload.coverage.limits}


# --- Calls: notes from a call's transcript are internal (default-deny) ----------------


def test_call_notes_never_reach_a_provider(seeded: Session) -> None:
    assert FactKind.CALL_NOTE not in SETTING_BY_KIND
    assert fact_visibility(FactKind.CALL_NOTE, mentions_strategy=False) is (
        Visibility.INTERNAL
    )
    note = _fact(seeded, FactKind.CALL_NOTE, ORTHO_ID)
    # Even mis-tagged shareable, about the share's own provider, its kind keeps it in.
    note.visibility = Visibility.SHAREABLE
    seeded.flush()

    assert note not in _visible(seeded, _share(provider=ORTHO_ID))


# --- D41: litigation events are internal (default-deny) -----------------------------


_EVERY_SETTING_COMBINATION = [
    ShareSettings.model_validate(
        {setting: bool(mask >> n & 1) for n, setting in enumerate(KINDS_BY_SETTING)}
    )
    for mask in range(2 ** len(KINDS_BY_SETTING))
]


@pytest.mark.parametrize("provider", [ORTHO_ID, THERAPY_ID, None])
def test_a_litigation_event_never_reaches_a_provider(
    seeded: Session, provider: int | None
) -> None:
    kind = FactKind.LITIGATION_EVENT
    assert kind not in SETTING_BY_KIND
    assert all(kind not in kinds for kinds in KINDS_BY_SETTING.values())
    assert fact_visibility(kind, mentions_strategy=False) is Visibility.INTERNAL
    filed = _fact(seeded, kind, None)
    # Even mis-tagged shareable and about a share's own provider, its kind keeps it in.
    event = _new_fact(seeded, kind, {"event": "dismissed"}, provider)
    for fact in (filed, event):
        fact.visibility = Visibility.SHAREABLE
    seeded.flush()

    for share_provider in (ORTHO_ID, THERAPY_ID):
        for settings in _EVERY_SETTING_COMBINATION:
            visible = _visible(
                seeded, _share(provider=share_provider, settings=settings)
            )
            assert filed not in visible and event not in visible


# --- D41: a status change reaches a provider only as a move to a named stage ---------


def test_a_status_change_without_a_stage_is_never_released(seeded: Session) -> None:
    free = _new_fact(
        seeded, FactKind.STATUS_CHANGE, {"to_stage": None, "label": "Free text"}, None
    )
    move = _new_fact(
        seeded,
        FactKind.STATUS_CHANGE,
        {"to_stage": "litigation", "label": "Free text"},
        None,
    )
    stage_off = ALL_ON.model_copy(update={"case_stage": False})

    for settings in _EVERY_SETTING_COMBINATION:
        assert free not in _visible(seeded, _share(settings=settings))
    assert move in _visible(seeded, _share())
    assert move not in _visible(seeded, _share(settings=stage_off))


# --- D35: an item's kind names only a bill or lien the link already shows ------------


def _items(payload: ProviderPayload) -> list[ProviderItemOut]:
    limits = payload.coverage.limits if payload.coverage else None
    sections = (payload.requests, payload.bills, payload.records, limits)
    return [item for section in sections for item in section or []]


def test_only_the_kinds_the_bills_setting_releases_are_named() -> None:
    assert set(ITEM_KIND_BY_FACT_KIND) == KINDS_BY_SETTING["own_bills"]
    assert NEVER_SHARED.isdisjoint(ITEM_KIND_BY_FACT_KIND)


@pytest.mark.parametrize("provider", [ORTHO_ID, THERAPY_ID])
def test_an_items_kind_is_set_only_on_a_released_bill_or_lien(
    seeded: Session, provider: int
) -> None:
    share = _share(provider=provider)
    released = {r.fact.id: r for r in visible_facts_for_share(seeded, share, NOW)}

    payload = provider_payload(seeded, share, NOW)

    labelled = [item for item in _items(payload) if item.kind is not None]
    assert labelled
    assert [item.fact_id for item in labelled] == [
        b.fact_id for b in payload.bills or []
    ]
    for item in labelled:
        assert item.fact_id in released
        assert released[item.fact_id].setting == "own_bills"
        assert item.kind == ITEM_KIND_BY_FACT_KIND[released[item.fact_id].fact.kind]


@pytest.mark.parametrize("withheld", ["hidden", "internal", "strategy", "bills_off"])
def test_a_withheld_lien_leaves_no_lien_kind(seeded: Session, withheld: str) -> None:
    lien = _fact(seeded, FactKind.LIEN, ORTHO_ID)
    share = _share()
    if withheld == "hidden":
        share = _share(hidden=[lien.id])
    elif withheld == "internal":
        lien.visibility = Visibility.INTERNAL
    elif withheld == "strategy":
        lien.mentions_strategy = True
    else:
        share = _share(settings=ALL_ON.model_copy(update={"own_bills": False}))
    seeded.flush()

    items = _items(provider_payload(seeded, share, NOW))

    assert lien.id not in {item.fact_id for item in items}
    assert "lien" not in {item.kind for item in items}


def test_an_internal_fact_never_becomes_a_labelled_item(seeded: Session) -> None:
    # Every never-shared fact, mis-tagged shareable and about the share's own provider.
    internal = list(seeded.scalars(select(Fact).where(Fact.kind.in_(NEVER_SHARED))))
    assert {fact.kind for fact in internal} == NEVER_SHARED
    for fact in internal:
        fact.visibility = Visibility.SHAREABLE
        fact.mentions_strategy = False
        fact.provider_contact_id = ORTHO_ID
    seeded.flush()

    items = _items(provider_payload(seeded, _share(), NOW))

    assert items
    assert {fact.id for fact in internal}.isdisjoint(item.fact_id for item in items)
