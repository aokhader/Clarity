"""Facts built in code read plainly: no raw ledger text, no stray whitespace.

A ledger fact's title was the Clio activity's own text, which firms fill with anything
(a provider saw a test entry's words as its bill), and the stage label kept Clio's
trailing space.
"""

from app.digest.mapping import LedgerEntry, _ledger_fact, _stage_facts
from app.models import FactKind, Source, SourceType
from app.schemas import CaseStage

PROVIDER = 60
RAW_TEXT = "Raw ledger words; typed by anyone"


def _activity(raw: dict) -> Source:
    return Source(
        matter_id=1, clio_type=SourceType.ACTIVITY, clio_id="80", raw_json=raw
    )


def test_a_medical_charge_on_the_ledger_has_a_neutral_title_with_its_date() -> None:
    activity = _activity(
        {"type": "ExpenseEntry", "date": "2020-02-01", "total": 120.0, "note": RAW_TEXT}
    )
    decision = LedgerEntry(
        activity_id=1, is_medical_charge=True, provider_contact_id=PROVIDER
    )

    fact = _ledger_fact(activity, decision, {PROVIDER: "Invented Clinic"})

    assert fact.kind is FactKind.MEDICAL_BILL
    assert fact.title == "Charges on the firm's ledger, Feb 1, 2020"


def test_a_firm_cost_takes_its_category_never_the_entry_text() -> None:
    with_category = _activity(
        {
            "type": "ExpenseEntry",
            "date": "2020-02-01",
            "total": 40.0,
            "note": RAW_TEXT,
            "expense_category": {"name": "Filing fee"},
        }
    )
    without = _activity({"type": "HardCostEntry", "total": 40.0, "note": RAW_TEXT})

    assert _ledger_fact(with_category, None, {}).title == "Filing fee"
    assert _ledger_fact(without, None, {}).title == "Firm expense"


def test_the_stage_label_has_no_trailing_space() -> None:
    matter = Source(
        matter_id=1,
        clio_type=SourceType.MATTER,
        clio_id="1",
        raw_json={"matter_stage": {"name": "Invented stage "}, "status": "Open"},
    )

    [fact] = _stage_facts(matter, CaseStage.TREATING)

    assert fact.title == "Stage: Invented stage"
    assert fact.quote == "Invented stage"
