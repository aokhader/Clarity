"""Which internal dates a draft must not state (D25, D28).

A date on its own discloses something only when it is the date of a negotiation, a
valuation or a limit, or of a legal deadline. Most deadlines in the data are calendar
entries or exam appointments; only a statute, court or filing deadline counts, read
from the type the data gives it.
"""

import re

from app.models import Fact, FactKind
from app.schemas import DeadlinePayload

# D25: the internal facts whose dates alone disclose something. A deadline counts
# only when it is a legal one (D28): see `_legal_deadline`.
SENSITIVE_DATE_KINDS = frozenset(
    {
        FactKind.OFFER,
        FactKind.DEMAND,
        FactKind.SETTLEMENT,
        FactKind.CASE_VALUE,
        FactKind.POLICY_LIMIT,
    }
)
# Words in a deadline's type that make it a statute, court or filing deadline (D28).
# Calendar entries, exams and untyped deadlines carry none of them.
LEGAL_DEADLINE_WORDS = frozenset(
    {
        "statute",
        "limitation",
        "limitations",
        "court",
        "filing",
        "file",
        "answer",
        "response",
        "reply",
        "motion",
        "hearing",
        "trial",
        "conference",
        "notice",
        "claim",
        "appeal",
        "discovery",
        "bill",
        "particulars",
    }
)


def sensitive_date(fact: Fact) -> bool:
    if fact.kind is FactKind.DEADLINE:
        return _legal_deadline(fact)
    return fact.kind in SENSITIVE_DATE_KINDS


def _legal_deadline(fact: Fact) -> bool:
    """A statute, court or filing deadline, by the type the data gives it (D28)."""
    kind = DeadlinePayload.model_validate(fact.value_json or {}).deadline_type or ""
    return bool(set(re.findall(r"[a-z]+", kind.lower())) & LEGAL_DEADLINE_WORDS)
