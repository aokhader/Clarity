"""Extraction keeps economic damages and recovery caps apart from specials and case
value, and records whose policy a limit belongs to (D19, D20, D21).

The extraction schema always allowed `medical_specials`, but no prompt said what it
was, so a total that added lost wages to the bills was filed there; a cap on recovery
was filed as a case value. A limit carried no word of whose policy it was.
"""

from collections import Counter
from typing import Any

import pytest

from app.digest import llm
from app.digest.extract import ExtractedFact, Extraction, Unit, _to_facts
from app.models import Fact, FactKind, Source, SourceType

QUOTE = "Invented line for a test"
POLICIES = ("defendant_liability", "client_no_fault", "client_um_uim", "client_other")
EXTRACTION_PROMPTS = ("extract_page", "extract_record")


def _fact_from(kind: str, amount: float | None, detail: dict[str, Any]) -> Fact:
    unit = Unit(
        source=Source(
            matter_id=1, clio_type=SourceType.NOTE, clio_id="n1", raw_json={}
        ),
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
                kind=kind, title="Invented", quote=QUOTE, amount=amount, detail=detail
            )
        ],
    )
    [fact] = _to_facts(unit, extraction, {}, Counter(), [])
    return fact


@pytest.mark.parametrize("prompt", EXTRACTION_PROMPTS)
def test_the_prompts_define_the_kinds_that_used_to_be_confused(prompt: str) -> None:
    text = llm.load_prompt(prompt).text
    for kind in ("medical_specials", "economic_damages", "recovery_cap", "case_value"):
        assert f"- {kind}:" in text, kind


@pytest.mark.parametrize("prompt", EXTRACTION_PROMPTS)
def test_the_prompts_name_every_policy_a_limit_can_belong_to(prompt: str) -> None:
    text = llm.load_prompt(prompt).text
    assert all(policy in text for policy in POLICIES)


def test_a_limit_keeps_whose_policy_it_is() -> None:
    fact = _fact_from(
        "policy_limit", 250.0, {"per": "person", "policy": "client_um_uim"}
    )
    assert fact.value_json["policy"] == "client_um_uim"
    assert fact.value_json["amount_cents"] == 25000


def test_a_policy_outside_the_list_is_unknown_and_the_limit_is_kept() -> None:
    fact = _fact_from("policy_limit", 250.0, {"per": "person", "policy": "someone's"})
    assert fact.value_json.get("policy") is None
    assert fact.value_json["amount_cents"] == 25000


@pytest.mark.parametrize("kind", ["economic_damages", "recovery_cap"])
def test_the_new_kinds_store_their_amount_in_cents_and_their_basis(kind: str) -> None:
    fact = _fact_from(kind, 900.5, {"basis": "Invented basis"})
    assert fact.kind is FactKind(kind)
    assert fact.value_json["amount_cents"] == 90050
    assert fact.value_json["basis"] == "Invented basis"
