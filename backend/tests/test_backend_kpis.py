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


def test_one_valuation_stated_as_a_figure_and_as_a_range_of_one_is_one_value(
    session: Session,
) -> None:
    as_range = _fact(
        session,
        FactKind.CASE_VALUE,
        {"low_cents": 900_00, "high_cents": 900_00},
        SourceType.MATTER,
    )
    as_figure = _fact(
        session, FactKind.CASE_VALUE, {"low_cents": 900_00, "high_cents": None}
    )

    tile = _tile([as_range, as_figure], "case_value")

    assert len(tile.values) == 1
    assert _ids(tile, 0) == {as_range.id, as_figure.id}


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


def test_coverage_shows_per_person_limits_when_the_file_states_them(
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

    assert [v.amount_cents for v in tile.values] == [1_000_00]
    assert tile.basis == "Per person"


def test_coverage_with_only_per_occurrence_limits_says_so(session: Session) -> None:
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
    assert tile.basis == "Matches the sum of 2 bills"


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
