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
from app.schemas import ShareSetting, ShareSettings, validate_payload
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


def test_a_limits_policy_does_not_change_whether_it_is_released(
    seeded: Session,
) -> None:
    limit = _new_fact(
        seeded,
        FactKind.POLICY_LIMIT,
        {"amount_cents": 2_500_00, "per": "person", "policy": "client_um_uim"},
        None,
    )
    limits_off = ALL_ON.model_copy(update={"coverage_limits": False})

    assert limit in _visible(seeded, _share())
    assert limit not in _visible(seeded, _share(settings=limits_off))
