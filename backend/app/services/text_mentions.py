"""Sentences and dates in free text, found with the standard library.

A date must name a month or use a full numeric form. Each mention keeps its character
span, so the UI can underline it, and the precision it was written at: a day, a month
and year, or a month and day. Money is read in `money_mentions.py`.
"""

import re
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from app.services.money_mentions import AmountMention
from app.services.money_mentions import find_amounts as find_money


class DatePrecision(StrEnum):
    DAY = "day"  # Jul 14, 2031
    MONTH = "month"  # July 2031
    MONTH_DAY = "month_day"  # Sept 6, with no year


@dataclass(frozen=True)
class DateMention:
    start: int
    end: int
    # The day written; the first of the month for MONTH; year 2000 for MONTH_DAY.
    on: date
    precision: DatePrecision

    def matches(self, day: date) -> bool:
        if self.precision is DatePrecision.DAY:
            return day == self.on
        if self.precision is DatePrecision.MONTH:
            return (day.year, day.month) == (self.on.year, self.on.month)
        return (day.month, day.day) == (self.on.month, self.on.day)


# --- Sentences ---------------------------------------------------------------------

# A sentence ends at . ! or ? before a capital, so "$1,234.56" and "Jul. 14" never split.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'(\[-])")
_LINE = re.compile(r"[^\r\n]+")
_LAST_WORD = re.compile(r"(\w+)\.$")
_ABBREVIATIONS = frozenset(
    {"dr", "mr", "mrs", "ms", "st", "jr", "sr", "no", "vs", "inc", "co", "ltd"}
)


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Each line, split into sentences: (start, end) offsets with whitespace trimmed."""
    spans: list[tuple[int, int]] = []
    for line in _LINE.finditer(text):
        begin = line.start()
        for end in _SENTENCE_END.finditer(text, line.start(), line.end()):
            word = _LAST_WORD.search(text, begin, end.start())
            if word and word.group(1).lower() in _ABBREVIATIONS:
                continue
            spans.append((begin, end.start()))
            begin = end.end()
        spans.append((begin, line.end()))
    trimmed = [_trim(text, start, end) for start, end in spans]
    return [(start, end) for start, end in trimmed if start < end]


def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


# --- Dates -------------------------------------------------------------------------

_MONTHS = {
    name: number
    for number, names in enumerate(
        [
            ("jan", "january"),
            ("feb", "february"),
            ("mar", "march"),
            ("apr", "april"),
            ("may",),
            ("jun", "june"),
            ("jul", "july"),
            ("aug", "august"),
            ("sep", "sept", "september"),
            ("oct", "october"),
            ("nov", "november"),
            ("dec", "december"),
        ],
        start=1,
    )
    for name in names
}
_MON = r"(?P<mon>[A-Za-z]{3,9})\.?"
_DAY = r"(?P<day>\d{1,2})(?:st|nd|rd|th)?"
_YEAR = r"(?P<year>\d{4})"
# Most specific first: a span taken by one form is not read again by a later one.
_DATE_FORMS: list[tuple[re.Pattern[str], DatePrecision]] = [
    (
        re.compile(r"\b(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})\b"),
        DatePrecision.DAY,
    ),
    (
        re.compile(r"\b(?P<month>\d{1,2})/(?P<day>\d{1,2})/(?P<year>\d{4}|\d{2})\b"),
        DatePrecision.DAY,
    ),
    (re.compile(rf"\b{_MON}\s+{_DAY},?\s+{_YEAR}\b"), DatePrecision.DAY),
    (re.compile(rf"\b{_DAY}\s+(?:of\s+)?{_MON},?\s+{_YEAR}\b"), DatePrecision.DAY),
    (re.compile(rf"\b{_MON},?\s+{_YEAR}\b"), DatePrecision.MONTH),
    (re.compile(rf"\b{_MON}\s+{_DAY}\b(?!,?\s*\d)"), DatePrecision.MONTH_DAY),
]
# Any year stands in for a date written without one; 2000 is a leap year, so Feb 29 fits.
_NO_YEAR = 2000


def _year(written: str) -> int:
    year = int(written)
    if len(written) == 2:
        # The POSIX rule that %y follows: 69-99 are 19xx, 00-68 are 20xx.
        year += 1900 if year >= 69 else 2000
    return year


def _date_of(match: re.Match[str]) -> date | None:
    groups = match.groupdict()
    if groups.get("mon") is not None:
        month = _MONTHS.get(groups["mon"].lower())
        if month is None:
            return None  # "Policy 2031" names no month
    else:
        month = int(groups["month"])
    year = _year(groups["year"]) if groups.get("year") else _NO_YEAR
    day = int(groups["day"]) if groups.get("day") else 1
    try:
        return date(year, month, day)
    except ValueError:
        return None  # "Feb 30" is not a date anyone can check


def find_dates(text: str) -> list[DateMention]:
    """Dates in the text: "Jul 14, 2031", "14 July 2031", "7/14/31", "2031-07-14",
    "July 2031" (a month), and "Sept 6" (no year)."""
    found: list[DateMention] = []
    for pattern, precision in _DATE_FORMS:
        for match in pattern.finditer(text):
            on = _date_of(match)
            if on is None or any(
                match.start() < d.end and d.start < match.end() for d in found
            ):
                continue
            found.append(DateMention(match.start(), match.end(), on, precision))
    return sorted(found, key=lambda d: d.start)


def find_amounts(text: str) -> list[AmountMention]:
    """Amounts written with a money marker. Bare numbers are left out: the call-notes
    check compares a note's figures with its quote's, where a year is not money."""
    return [amount for amount in find_money(text) if amount.marked]
