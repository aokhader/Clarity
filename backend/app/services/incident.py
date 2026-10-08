"""The facts behind the header's date of incident and its account of what happened.

A matter can hold hundreds of incident facts, most read from documents that describe
the collision without dating it. The header cites one, and its chip must open a source
that shows the date. So the firm's own date-of-incident field in Clio (mapped in code)
decides the date when it is set; otherwise the date most facts state does. Among the
facts on that date, one whose quote writes the date out is cited first.

The field fact dates the incident but cannot describe it: its title is the field's
label. The account of what happened is the one most records read on that day give.
Titles are used rather than descriptions, which are often fragments of a page.
"""

import re
from collections import Counter
from datetime import date

from app.models import Fact, Origin
from app.services.restatements import group_restatements
from app.services.text_mentions import DatePrecision, find_dates

# Words that say only that something happened at some time. A title made of these,
# dates and clock times names no event, so it cannot be the account of one.
_TIME_WORDS = frozenset(
    {"accident", "incident", "loss", "injury", "doi", "dol", "date", "dated", "day"}
    | {"time", "occurred", "occurrence", "happened", "on", "of", "at", "in", "or"}
    | {"about", "around", "approximately", "approx", "the", "a", "an", "was", "is"}
    | {"am", "pm", "hours", "hrs", "monday", "tuesday", "wednesday", "thursday"}
    | {"friday", "saturday", "sunday", "january", "february", "march", "april"}
    | {"june", "july", "august", "september", "october", "november", "december"}
)
_CLOCK = re.compile(
    r"\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:[ap]\.?m\b\.?)?"
    r"|\b\d{1,2}\s*[ap]\.?m\b\.?"
    r"|\b\d{3,4}\s*(?:hours|hrs)\b",
    re.IGNORECASE,
)
_WORD = re.compile(r"[a-z0-9]+")
_NUMBER = re.compile(r"\d+(?:st|nd|rd|th)?")


def _incident_day(dated: list[Fact]) -> date | None:
    if not dated:
        return None
    field = [f for f in dated if f.origin is Origin.CODE]
    if field:
        return max(field, key=lambda f: f.significance).event_date
    counts = Counter(f.event_date for f in dated)
    # Ties go to the later date, as the most recent account of the same event.
    return max(counts, key=lambda d: (counts[d], d))


def incident_fact(facts: list[Fact]) -> Fact | None:
    dated = [f for f in facts if f.event_date is not None]
    day = _incident_day(dated)
    if day is None:
        return None
    on_day = [f for f in dated if f.event_date == day]
    return max(
        on_day,
        key=lambda f: (_quote_shows(f, day), f.origin is Origin.CODE, f.significance),
    )


def incident_account(facts: list[Fact]) -> list[Fact]:
    """The account of the incident most records give: the leading fact of the group
    of model reads on the header's incident day that restate one another and come from
    the most records, then the rest of that group. Empty when no read on that day
    names an event.

    A title that only restates the date is left out, however many records give it.
    Records are counted, not facts, so one document restating an account on every page
    counts once. A tie goes to the group whose leading fact is more significant, then
    to the lower id. Never the field fact.
    """
    day = _incident_day([f for f in facts if f.event_date is not None])
    if day is None:
        return []
    told = sorted(
        (
            f
            for f in facts
            if f.event_date == day
            and f.origin is Origin.MODEL
            and names_an_event(f.title)
        ),
        key=lambda f: (-f.significance, f.id),
    )
    # In that order, each group's first fact is its most significant one.
    groups = group_restatements(told)
    return min(
        groups,
        key=lambda g: (-_records(g), -g[0].significance, g[0].id),
        default=[],
    )


def _records(group: list[Fact]) -> int:
    return len({f.source_id for f in group})


def names_an_event(title: str) -> bool:
    """Whether a title says more than when: something is left once its dates, clock
    times and words of time are taken out."""
    text = title
    for mention in reversed(find_dates(title)):
        text = f"{text[: mention.start]} {text[mention.end :]}"
    words = _WORD.findall(_CLOCK.sub(" ", text).lower())
    return any(w not in _TIME_WORDS and not _NUMBER.fullmatch(w) for w in words)


def _quote_shows(fact: Fact, day: date) -> bool:
    return any(
        mention.precision is DatePrecision.DAY and mention.on == day
        for mention in find_dates(fact.quote or "")
    )
