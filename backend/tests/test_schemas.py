import pytest
from pydantic import ValidationError

from app.models import FactKind
from app.schemas import PAYLOAD_BY_KIND, validate_payload


def test_every_fact_kind_has_a_payload_model() -> None:
    assert set(PAYLOAD_BY_KIND) == set(FactKind)


def test_unknown_payload_keys_are_rejected() -> None:
    with pytest.raises(ValidationError):
        validate_payload(FactKind.MEDICAL_BILL, {"amount": 12.5})


def test_payload_is_stored_with_every_key() -> None:
    stored = validate_payload(FactKind.MEDICAL_BILL, {"amount_cents": 1250})
    assert stored == {
        "alt_values": [],
        "corroborating_source_ids": [],
        "amount_cents": 1250,
        "balance_cents": None,
    }
