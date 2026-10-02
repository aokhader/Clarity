from datetime import date

from app.digest.verify import compare_reads, quote_in_text, resolve_provider, sane_date
from app.models import Confidence, FactKind

PAGE = "Patient seen for follow-up.\nImpression:  sprain of the left wrist.\nCharge: $250.00"


def test_quote_present_after_whitespace_normalization_passes() -> None:
    assert quote_in_text("Impression: sprain of the left wrist.", PAGE)


def test_quote_not_in_input_fails() -> None:
    assert not quote_in_text("fracture of the right ankle", PAGE)
    assert not quote_in_text("", PAGE)


def test_agreeing_second_read_verifies() -> None:
    outcome = compare_reads(250.0, date(2024, 3, 1), 250.0, date(2024, 3, 1))
    assert outcome.verified and outcome.confidence is Confidence.HIGH


def test_disagreeing_second_read_gives_low_confidence_and_keeps_both() -> None:
    outcome = compare_reads(250.0, date(2024, 3, 1), 280.0, date(2024, 3, 1))
    assert not outcome.verified
    assert outcome.confidence is Confidence.LOW
    assert outcome.alt_values and outcome.alt_values[0]["amount_cents"] == 28000


def test_future_date_on_past_tense_kind_is_removed() -> None:
    today = date(2025, 1, 1)
    assert sane_date(FactKind.MEDICAL_BILL, date(2026, 1, 1), today) is None
    assert sane_date(FactKind.DEADLINE, date(2026, 1, 1), today) == date(2026, 1, 1)
    assert sane_date(FactKind.INJURY, date(1990, 1, 1), today) is None


def test_provider_resolution_needs_one_clear_match() -> None:
    providers = {1: "Example Physical Therapy, P.C.", 2: "Example Imaging LLC"}
    assert resolve_provider("EXAMPLE PHYSICAL THERAPY", providers) == 1
    assert resolve_provider("Example", providers) is None
    assert resolve_provider(None, providers) is None
