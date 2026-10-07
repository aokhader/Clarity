"""Money in free text, found with the standard library (D25).

An attorney can write a figure many ways, and the draft checker must catch every one
that discloses an internal amount. A number is read as money when it carries a marker:
a dollar sign before or after it (full-width too), USD, "dollars", "bucks", "grand" or a
"k" suffix. A number with no marker is read only when it has four digits or more, or is
written out in words of a thousand or more; it is kept apart (`marked=False`), because
it may be a reference number or a year and only an exact match means anything.

Each amount keeps the precision it was written at, so "$12k" is compared to the nearest
$1,000, and the coarser precision the writer may have rounded to ("$330,000" may be a
figure rounded to $10,000). Two amounts joined as a range ("$300k-$350k") are returned
as a range too.
"""

import re
from dataclasses import dataclass
from decimal import Decimal
from itertools import pairwise

# Below this, "rounds to" is not inferred from trailing zeros: "$1,000" is too often
# a figure of its own, and small internal figures (fees, copays) are not the risk.
ROUNDING_FROM_CENTS = 10_000_00
# A range locks only when narrow enough to say something: high is at most twice low.
RANGE_SPREAD = 2


@dataclass(frozen=True)
class AmountMention:
    start: int
    end: int
    cents: int
    # Half the smallest unit written: 50 for "$2,480", 0 for "$2,480.50", $500 for "$12k".
    tolerance_cents: int
    # Half the unit the writer may have rounded to: $5,000 for "$330,000". Never less
    # than tolerance_cents.
    rounding_cents: int
    marked: bool  # carries a money marker; False for bare digits or words
    scale: int  # 1, 1,000 or 1,000,000: the multiplier written ("k", "million")

    def matches(self, cents: int) -> bool:
        """The written figure, at the precision written."""
        return abs(cents - self.cents) <= self.tolerance_cents

    def rounds_from(self, cents: int) -> bool:
        """`cents` rounded to the precision the writer may have used gives this figure."""
        return abs(cents - self.cents) <= self.rounding_cents


@dataclass(frozen=True)
class AmountRange:
    """Two amounts joined as a range: "$300k-$350k", "between $1,000 and $1,500"."""

    low: AmountMention
    high: AmountMention

    @property
    def low_cents(self) -> int:
        # "$300-350k": the scale written once applies to both ends.
        if self.low.scale == 1 and self.high.scale > 1:
            scaled = self.low.cents * self.high.scale
            if scaled <= self.high.cents:
                return scaled
        return self.low.cents

    def brackets(self, cents: int) -> bool:
        low = self.low_cents
        return (
            0 < low <= cents <= self.high.cents
            and self.high.cents <= RANGE_SPREAD * low
        )


# --- Numbers written in digits -------------------------------------------------------

_DOLLAR = "$\uff04\ufe69"  # dollar sign, full-width, small
# Thousands grouped by commas, thin or no-break spaces, dots, plain spaces or
# apostrophes; or plain digits. A plain space or an apostrophe groups thousands
# only beside a money marker (`_numeric`): "12 345 visits" is two numbers.
_GROUPED = r"\d{1,3}(?:(?:,|[\u2009\u202f\u00a0 '\u2019]|\.)\d{3})+(?!\d)(?!,\d)"
_NUMERIC = re.compile(
    rf"(?P<prefix>US[{_DOLLAR}]|[{_DOLLAR}]|\bUSD)?\s?"
    rf"(?<![\w.,/:+#])(?P<num>{_GROUPED}|\d+)(?:\.(?P<frac>\d+))?(?![\d/:])"
    r"(?:\s?(?P<scale>k|mm|m|thousand|million|grand)\b)?"
    rf"(?:\s?(?P<suffix>[{_DOLLAR}]|USD\b|dollars?\b|bucks\b))?",
    re.IGNORECASE,
)
_LOOSE_SEPARATOR = re.compile("[ '\u2019]")
_SCALES = {
    "k": 1_000,
    "thousand": 1_000,
    "grand": 1_000,
    "m": 1_000_000,
    "mm": 1_000_000,
    "million": 1_000_000,
}
# These carry their own meaning of money: "12k", "12 grand".
_MONEY_SCALES = {"k", "grand"}


def _numeric(match: re.Match[str]) -> AmountMention | None:
    num, frac = match["num"], match["frac"] or ""
    text = match.string
    scale_word = (match["scale"] or "").lower()
    scale = _SCALES.get(scale_word, 1)
    if "." in num and not frac and scale == 1:
        num = num.replace(".", "")  # dots grouping thousands: "123.456"
    elif "." in num:
        # "$2.125 million": the dot is a decimal point after all.
        whole, _, rest = num.partition(".")
        num, frac = whole, rest.replace(".", "") + frac
    digits = re.sub(r"\D", "", num)
    marked = bool(match["prefix"] or match["suffix"] or scale_word in _MONEY_SCALES)
    if not marked and len(digits) < 4 and scale == 1:
        return None  # a bare "3" or "250" is not money
    if not marked and _LOOSE_SEPARATOR.search(num):
        return None  # "12 345 visits": two numbers, not a figure
    hyphened = text[match.start("num") - 1 : match.start("num")] == "-" or (
        text[match.end() : match.end() + 1] == "-"
    )
    if not marked and hyphened:
        return None  # part of a phone number, an id or a date: "555-0100"
    dollars = Decimal(digits + (f".{frac}" if frac else "")) * scale
    unit = Decimal(scale) / Decimal(10) ** len(frac)
    return _mention(match.start(), match.end(), dollars, unit, marked, scale)


# --- Numbers written in words ---------------------------------------------------------

_UNIT_WORDS = [
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
]  # fmt: skip
_TEN_WORDS = [
    "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety",
]  # fmt: skip
_UNITS = {word: n for n, word in enumerate(_UNIT_WORDS)}
_TENS = {word: 10 * n for n, word in enumerate(_TEN_WORDS, start=2)}
_WORD_SCALES = {"thousand": 1_000, "grand": 1_000, "million": 1_000_000}
# Longest first, so "seventeen" is not read as "seven".
_NUMBER_WORD = "|".join(
    sorted([*_UNITS, *_TENS, "hundred", *_WORD_SCALES], key=len, reverse=True)
)
_WORDS = re.compile(
    rf"\b(?P<words>(?:{_NUMBER_WORD})\b(?:(?:\s+and\s+|[\s-]+)(?:{_NUMBER_WORD})\b)*)"
    r"(?:\s+(?P<suffix>dollars?|bucks)\b)?",
    re.IGNORECASE,
)


def _words(match: re.Match[str]) -> AmountMention | None:
    words = match["words"].lower()
    total = current = 0
    for word in re.split(r"[\s-]+", words):
        if word in _UNITS:
            current += _UNITS[word]
        elif word in _TENS:
            current += _TENS[word]
        elif word == "hundred":
            current = (current or 1) * 100
        elif word in _WORD_SCALES:
            total += (current or 1) * _WORD_SCALES[word]
            current = 0
    value = total + current
    marked = bool(match["suffix"]) or "grand" in words
    if not marked and value < 1_000:
        return None  # "two visits" is not money
    return _mention(match.start(), match.end(), Decimal(value), Decimal(1), marked, 1)


# --- Shared ------------------------------------------------------------------------


def _mention(
    start: int, end: int, dollars: Decimal, unit: Decimal, marked: bool, scale: int
) -> AmountMention:
    cents = int(dollars * 100)
    tolerance = int(unit * 100 / 2)
    rounding = tolerance
    if (
        marked
        and cents >= ROUNDING_FROM_CENTS
        and dollars == dollars.to_integral_value()
    ):
        whole = int(dollars)
        zeros = len(str(whole)) - len(str(whole).rstrip("0"))
        rounding = max(tolerance, 10**zeros * 100 // 2)
    return AmountMention(start, end, cents, tolerance, rounding, marked, scale)


def find_amounts(text: str) -> list[AmountMention]:
    """Every amount in the text, in order, none overlapping another."""
    found = [m for m in map(_numeric, _NUMERIC.finditer(text)) if m is not None]
    found += [m for m in map(_words, _WORDS.finditer(text)) if m is not None]
    kept: list[AmountMention] = []
    # A marked reading wins over a bare one of the same words; then the longer one.
    for amount in sorted(found, key=lambda a: (a.start, not a.marked, -a.end)):
        if not any(amount.start < k.end and k.start < amount.end for k in kept):
            kept.append(amount)
    return sorted(kept, key=lambda a: a.start)


_RANGE_JOIN = re.compile(r"\s*(?:-|\u2013|\u2014|to|and)\s*", re.IGNORECASE)
_BETWEEN = re.compile(r"between\s*$", re.IGNORECASE)


def find_ranges(text: str, amounts: list[AmountMention]) -> list[AmountRange]:
    """Pairs of neighbouring amounts written as a range."""
    ranges = []
    for low, high in pairwise(amounts):
        join = text[low.end : high.start]
        if not _RANGE_JOIN.fullmatch(join):
            continue
        if join.strip().lower() == "and" and not _BETWEEN.search(text[: low.start]):
            continue  # "$100 and $200" lists two amounts; "between ... and" is a range
        ranges.append(AmountRange(low, high))
    return ranges
