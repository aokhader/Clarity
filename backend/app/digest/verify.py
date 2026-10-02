"""Stage 4: checks every model-origin fact passes before it is stored.

1. Quote check: the quote must appear in the input. Text inputs that fail are dropped.
   Scans have no text to match, so their facts are kept at medium confidence.
2. Second read: money and dates on scans are read twice; disagreement means low confidence.
3. Date sanity: future dates on past-tense kinds and very old dates are removed.
4. Provider resolution: a provider named on the page is matched to a known contact.
"""

import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from app.models import Confidence, FactKind

MAX_AGE = timedelta(days=365 * 20)
SECOND_READ_KINDS = {
    FactKind.MEDICAL_BILL,
    FactKind.LIEN,
    FactKind.POLICY_LIMIT,
    FactKind.DEMAND,
    FactKind.OFFER,
    FactKind.SETTLEMENT,
    FactKind.DEADLINE,
}
# Kinds that describe something that has already happened, so a future date is wrong.
PAST_TENSE_KINDS = {
    FactKind.INJURY,
    FactKind.DIAGNOSIS,
    FactKind.MEDICAL_BILL,
    FactKind.LIEN,
    FactKind.RECORDS_RECEIVED,
    FactKind.DEMAND,
    FactKind.OFFER,
    FactKind.SETTLEMENT,
    FactKind.EXPENSE,
    FactKind.CLIENT_CONTACT,
    FactKind.STATUS_CHANGE,
}
_QUOTE_CHARS = str.maketrans(
    {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", " ": " "}
)
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
# Words that say nothing about which provider a name refers to.
_NAME_NOISE = {
    "md",
    "do",
    "dc",
    "pt",
    "pc",
    "pllc",
    "llc",
    "inc",
    "the",
    "of",
    "and",
    "dr",
}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(_QUOTE_CHARS).lower()
    return " ".join(text.split())


def quote_in_text(quote: str | None, text: str) -> bool:
    if not quote or not quote.strip():
        return False
    return normalize(quote) in normalize(text)


@dataclass
class SecondReadOutcome:
    confidence: Confidence
    verified: bool
    alt_values: list[dict[str, object]] | None


def compare_reads(
    first_amount: float | None,
    first_date: date | None,
    second_amount: float | None,
    second_date: date | None,
) -> SecondReadOutcome:
    """Agreement on every value the first read produced makes the fact verified."""
    amounts_agree = first_amount is None or (
        second_amount is not None and abs(first_amount - second_amount) < 0.005
    )
    dates_agree = first_date is None or first_date == second_date
    if amounts_agree and dates_agree:
        return SecondReadOutcome(Confidence.HIGH, True, None)
    return SecondReadOutcome(
        Confidence.LOW,
        False,
        [
            {
                "amount": second_amount,
                "event_date": second_date.isoformat() if second_date else None,
                "read": "second",
            }
        ],
    )


def sane_date(
    kind: FactKind, value: date | None, today: date | None = None
) -> date | None:
    if value is None:
        return None
    today = today or datetime.now(UTC).date()
    if kind in PAST_TENSE_KINDS and value > today:
        return None
    if value < today - MAX_AGE:
        return None
    return value


def name_tokens(name: str) -> set[str]:
    return {t for t in _NON_ALNUM.split(normalize(name)) if t and t not in _NAME_NOISE}


def resolve_provider(
    name_as_written: str | None, providers: dict[int, str]
) -> int | None:
    """Match a written name to exactly one known provider, or return None."""
    if not name_as_written:
        return None
    written = name_tokens(name_as_written)
    if not written:
        return None
    matches = [
        contact_id
        for contact_id, name in providers.items()
        if (tokens := name_tokens(name)) and (tokens <= written or written <= tokens)
    ]
    return matches[0] if len(matches) == 1 else None
