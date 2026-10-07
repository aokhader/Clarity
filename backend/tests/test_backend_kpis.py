"""KPI tiles: one value per figure the file states, the best-supported figure first."""

from typing import Any

from sqlalchemy.orm import Session

from app.models import Confidence, Fact, FactKind, Origin, Source, SourceType
from app.schemas import KpiOut
from app.services.kpis import kpi_tiles

MATTER = 7
PROVIDER = 55


def _fact(
    session: Session,
    kind: FactKind,
    value: dict[str, Any],
    clio_type: SourceType = SourceType.NOTE,
    significance: int = 50,
    provider: int | None = None,
) -> Fact:
    source = Source(
        matter_id=MATTER,
        clio_type=clio_type,
        clio_id=f"{clio_type}-{session.query(Source).count()}",
        raw_json={},
    )
    session.add(source)
    session.flush()
    fact = Fact(
        matter_id=MATTER,
        kind=kind,
        title="Figure",
        value_json=value,
        source_id=source.id,
        page_no=1 if clio_type is SourceType.DOCUMENT else None,
        provider_contact_id=provider,
        significance=significance,
        confidence=Confidence.HIGH,
        origin=Origin.MODEL,
    )
    session.add(fact)
    session.flush()
    return fact


def _tile(facts: list[Fact], name: str) -> KpiOut:
    by_kind: dict[FactKind, list[Fact]] = {kind: [] for kind in FactKind}
    for fact in facts:
        by_kind[fact.kind].append(fact)
    return next(tile for tile in kpi_tiles(by_kind) if tile.name == name)


def _ids(tile: KpiOut, index: int) -> set[int]:
    return {ref.id for ref in tile.values[index].facts}


def test_a_one_ended_valuation_stays_one_ended(session: Session) -> None:
    point = _fact(
        session,
        FactKind.CASE_VALUE,
        {"low_cents": 900_00, "high_cents": 900_00},
        SourceType.MATTER,
    )
    at_least = _fact(
        session, FactKind.CASE_VALUE, {"low_cents": 900_00, "high_cents": None}
    )

    tile = _tile([point, at_least], "case_value")

    assert {(v.low_cents, v.high_cents) for v in tile.values} == {
        (900_00, 900_00),
        (900_00, None),
    }


def test_the_figure_more_records_state_comes_first(session: Session) -> None:
    once = _fact(
        session,
        FactKind.CASE_VALUE,
        {"low_cents": 100_00, "high_cents": 100_00},
        significance=95,
    )
    twice = [
        _fact(
            session,
            FactKind.CASE_VALUE,
            {"low_cents": 700_00, "high_cents": 700_00},
            significance=60,
        )
        for _ in range(2)
    ]

    tile = _tile([once, *twice], "case_value")

    assert [v.low_cents for v in tile.values] == [700_00, 100_00]


def test_coverage_lists_every_limit_labelled_per_person_first(
    session: Session,
) -> None:
    per_person = _fact(
        session, FactKind.POLICY_LIMIT, {"amount_cents": 1_000_00, "per": "person"}
    )
    per_occurrence = _fact(
        session,
        FactKind.POLICY_LIMIT,
        {"amount_cents": 3_000_00, "per": "occurrence"},
        significance=99,
    )
    unstated = _fact(session, FactKind.POLICY_LIMIT, {"amount_cents": 2_000_00})

    tile = _tile([per_person, per_occurrence, unstated], "coverage")

    assert [(v.amount_cents, v.label) for v in tile.values] == [
        (1_000_00, "Per person"),
        (3_000_00, "Per occurrence"),
        (2_000_00, None),
    ]
    # The values are of different kinds, so no one basis describes them all.
    assert tile.basis is None


def test_one_amount_stated_per_person_and_per_occurrence_is_two_values(
    session: Session,
) -> None:
    limits = [
        _fact(session, FactKind.POLICY_LIMIT, {"amount_cents": 500_00, "per": per})
        for per in ("person", "occurrence")
    ]

    tile = _tile(limits, "coverage")

    assert [v.label for v in tile.values] == ["Per person", "Per occurrence"]


def test_coverage_of_one_kind_names_it_in_the_basis(session: Session) -> None:
    limit = _fact(
        session,
        FactKind.POLICY_LIMIT,
        {"amount_cents": 3_000_00, "per": "occurrence"},
    )

    tile = _tile([limit], "coverage")

    assert [v.amount_cents for v in tile.values] == [3_000_00]
    assert tile.basis == "Per occurrence"


def test_specials_the_bills_confirm_lead_a_figure_only_one_record_states(
    session: Session,
) -> None:
    misread = _fact(
        session, FactKind.MEDICAL_SPECIALS, {"amount_cents": 900_00}, significance=95
    )
    stated = _fact(
        session,
        FactKind.MEDICAL_SPECIALS,
        {"amount_cents": 300_00},
        SourceType.MATTER,
        significance=60,
    )
    bills = [
        _fact(
            session,
            FactKind.MEDICAL_BILL,
            {"amount_cents": cents},
            SourceType.DOCUMENT,
            provider=PROVIDER,
        )
        for cents in (100_00, 200_00)
    ]

    tile = _tile([misread, stated, *bills], "medical_specials")

    assert [v.amount_cents for v in tile.values] == [300_00, 900_00]
    assert _ids(tile, 0) == {stated.id, *(b.id for b in bills)}
    # Two figures, so the tile warns that sources disagree; the basis must not also
    # say the tile "matches".
    assert tile.basis == "The first figure is the sum of 2 bills"


def test_specials_the_bills_confirm_lead_even_when_restated_less(
    session: Session,
) -> None:
    misread = [
        _fact(session, FactKind.MEDICAL_SPECIALS, {"amount_cents": 900_00})
        for _ in range(3)
    ]
    stated = _fact(
        session, FactKind.MEDICAL_SPECIALS, {"amount_cents": 300_00}, SourceType.MATTER
    )
    bill = _fact(
        session,
        FactKind.MEDICAL_BILL,
        {"amount_cents": 300_00},
        SourceType.DOCUMENT,
        provider=PROVIDER,
    )

    tile = _tile([*misread, stated, bill], "medical_specials")

    assert [v.amount_cents for v in tile.values] == [300_00, 900_00]


def test_specials_one_figure_the_bills_confirm_matches(session: Session) -> None:
    stated = _fact(
        session, FactKind.MEDICAL_SPECIALS, {"amount_cents": 300_00}, SourceType.MATTER
    )
    bill = _fact(
        session,
        FactKind.MEDICAL_BILL,
        {"amount_cents": 300_00},
        SourceType.DOCUMENT,
        provider=PROVIDER,
    )

    tile = _tile([stated, bill], "medical_specials")

    assert len(tile.values) == 1
    assert tile.basis == "Matches the sum of 1 bill"


def test_specials_no_bill_sum_confirms_keep_the_stated_figure_first(
    session: Session,
) -> None:
    stated = _fact(
        session, FactKind.MEDICAL_SPECIALS, {"amount_cents": 900_00}, SourceType.MATTER
    )
    bill = _fact(
        session,
        FactKind.MEDICAL_BILL,
        {"amount_cents": 100_00},
        SourceType.DOCUMENT,
        provider=PROVIDER,
    )

    tile = _tile([stated, bill], "medical_specials")

    assert [v.amount_cents for v in tile.values] == [900_00, 100_00]
    assert tile.basis == "Differs from the sum of 1 bill"


# --- B10 (D19): whose policy a limit belongs to ---------------------------------------


def _limit(
    session: Session, cents: int, per: str | None, policy: str | None = None
) -> Fact:
    value: dict[str, Any] = {"amount_cents": cents, "per": per, "policy": policy}
    return _fact(session, FactKind.POLICY_LIMIT, value)


def test_coverage_leads_with_the_defendants_limit_and_labels_the_clients(
    session: Session,
) -> None:
    facts = [
        _limit(session, 25_000_00, "person", "client_um_uim"),
        _limit(session, 50_000_00, "person", "client_no_fault"),
        _limit(session, 100_000_00, "person", "defendant_liability"),
        _limit(session, 300_000_00, "occurrence", "defendant_liability"),
    ]

    tile = _tile(facts, "coverage")

    assert [(v.amount_cents, v.label) for v in tile.values] == [
        (100_000_00, "Defendant liability, per person"),
        (300_000_00, "Defendant liability, per occurrence"),
        (50_000_00, "Client no-fault, per person"),
        (25_000_00, "Client UM/UIM, per person"),
    ]
    # Different policies are separate entries, not a disagreement.
    assert tile.sources_disagree is False


def test_two_figures_for_the_same_policy_disagree(session: Session) -> None:
    facts = [
        _limit(session, 100_000_00, "person", "defendant_liability"),
        _limit(session, 50_000_00, "person", "defendant_liability"),
    ]

    assert _tile(facts, "coverage").sources_disagree is True


def test_limits_of_unknown_policy_show_as_before(session: Session) -> None:
    facts = [
        _limit(session, 100_000_00, "person"),
        _limit(session, 50_000_00, "person"),
        _limit(session, 300_000_00, "occurrence"),
    ]

    tile = _tile(facts, "coverage")

    assert [v.label for v in tile.values] == [
        "Per person",
        "Per person",
        "Per occurrence",
    ]
    assert tile.sources_disagree is True


def test_an_unknown_policy_stating_the_same_figure_does_not_disagree(
    session: Session,
) -> None:
    facts = [
        _limit(session, 100_000_00, "person", "defendant_liability"),
        _limit(session, 100_000_00, "person"),
    ]

    assert _tile(facts, "coverage").sources_disagree is False


def test_other_tiles_disagree_when_they_hold_two_figures(session: Session) -> None:
    one = _fact(session, FactKind.EXPENSE, {"amount_cents": 100_00})
    specials = [
        _fact(session, FactKind.MEDICAL_SPECIALS, {"amount_cents": cents})
        for cents in (100_00, 200_00)
    ]

    assert _tile([one], "firm_spend").sources_disagree is False
    assert _tile(specials, "medical_specials").sources_disagree is True


# --- K1: the valuation leads the Case value tile ---------------------------------------


def test_the_firms_valuation_field_leads_over_a_more_significant_cap(
    session: Session,
) -> None:
    cap = _fact(
        session,
        FactKind.CASE_VALUE,
        {"low_cents": 100_000_00, "high_cents": 100_000_00, "basis": "policy limit"},
        significance=99,
    )
    damages = _fact(
        session,
        FactKind.CASE_VALUE,
        {"low_cents": 300_000_00, "high_cents": None, "basis": "losses so far"},
        significance=95,
    )
    note = _fact(
        session,
        FactKind.CASE_VALUE,
        {"low_cents": 400_000_00, "high_cents": None, "basis": "the valuation memo"},
        significance=90,
    )
    field = _fact(
        session,
        FactKind.CASE_VALUE,
        {"low_cents": 400_000_00, "high_cents": 400_000_00, "basis": "Value field"},
        SourceType.MATTER,
        significance=50,
    )
    field.origin = Origin.CODE
    session.flush()

    tile = _tile([cap, damages, note, field], "case_value")

    assert [(v.low_cents, v.high_cents) for v in tile.values][:2] == [
        (400_000_00, 400_000_00),
        (400_000_00, None),
    ]
    assert _ids(tile, 0) == {field.id}
    assert (tile.values[-1].low_cents, tile.values[-1].high_cents) == (
        100_000_00,
        100_000_00,
    )
    # The basis explains the valuation, from the note that states the same figure.
    assert tile.basis == "the valuation memo"
    assert tile.sources_disagree is True  # the cap still contradicts the valuation


def test_at_least_a_figure_agrees_with_that_figure(session: Session) -> None:
    point = _fact(
        session,
        FactKind.CASE_VALUE,
        {"low_cents": 400_000_00, "high_cents": 400_000_00},
    )
    at_least = _fact(
        session, FactKind.CASE_VALUE, {"low_cents": 300_000_00, "high_cents": None}
    )

    tile = _tile([point, at_least], "case_value")

    assert len(tile.values) == 2
    assert tile.sources_disagree is False
