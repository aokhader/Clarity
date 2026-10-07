"""The model reports every sum in dollars; stored payloads hold integer cents.

The extraction prompts once asked for `balance_cents` and `high_cents` by name while
saying all amounts are dollars, and the code stored those keys unconverted, so a
balance or a high estimate could land 100 times too small.
"""

from collections import Counter
from typing import Any

import pytest

from app.digest import llm
from app.digest.extract import ExtractedFact, Extraction, Unit, _to_facts
from app.models import Fact, FactKind, Source, SourceType

QUOTE = "Invented line for a test"


def _facts_from(
    kind: FactKind, amount: float | None, detail: dict[str, Any]
) -> list[Fact]:
    source = Source(matter_id=1, clio_type=SourceType.NOTE, clio_id="n1", raw_json={})
    unit = Unit(
        source=source,
        text=QUOTE,
        request=llm.ModelRequest(
            purpose="extract_record",
            role="extract",
            prompt=llm.load_prompt("extract_record"),
            user_text=QUOTE,
            output=Extraction,
        ),
    )
    extraction = Extraction(
        document_type="other",
        facts=[
            ExtractedFact(
                kind=kind.value,
                title="Invented",
                quote=QUOTE,
                amount=amount,
                detail=detail,
            )
        ],
    )
    return _to_facts(unit, extraction, {}, Counter(), [])


@pytest.mark.parametrize("prompt", ["extract_page", "extract_record"])
def test_extraction_prompts_ask_for_no_sum_in_cents(prompt: str) -> None:
    assert "_cents" not in llm.load_prompt(prompt).text


def test_a_bill_balance_given_in_dollars_is_stored_in_cents() -> None:
    [fact] = _facts_from(FactKind.MEDICAL_BILL, 180.0, {"balance": 45.5})
    assert fact.value_json["amount_cents"] == 18000
    assert fact.value_json["balance_cents"] == 4550


def test_a_case_value_range_given_in_dollars_is_stored_in_cents() -> None:
    [fact] = _facts_from(FactKind.CASE_VALUE, 400.0, {"high": "$650.75", "basis": "x"})
    assert fact.value_json["low_cents"] == 40000
    assert fact.value_json["high_cents"] == 65075


def test_a_cents_key_volunteered_by_the_model_is_not_trusted() -> None:
    # The model is asked for dollars only, so a key named in cents has an unknown unit.
    [fact] = _facts_from(
        FactKind.MEDICAL_BILL, 180.0, {"balance_cents": 45, "amount_cents": 7}
    )
    assert fact.value_json["amount_cents"] == 18000
    assert fact.value_json.get("balance_cents") is None
