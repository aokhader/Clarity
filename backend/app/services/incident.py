"""The fact behind the header's date of incident.

A matter can hold hundreds of incident facts, most read from documents that describe
the collision without dating it. The header cites one, and its chip must open a source
that shows the date. So the firm's own date-of-incident field in Clio (mapped in code)
decides the date when it is set; otherwise the date most facts state does. Among the
facts on that date, one whose quote writes the date out is cited first.
"""

from collections import Counter
from datetime import date

from app.models import Fact, Origin
from app.services.text_mentions import DatePrecision, find_dates


def incident_fact(facts: list[Fact]) -> Fact | None:
    dated = [f for f in facts if f.event_date is not None]
    if not dated:
        return None
    field = [f for f in dated if f.origin is Origin.CODE]
    if field:
        day = max(field, key=lambda f: f.significance).event_date
    else:
        counts = Counter(f.event_date for f in dated)
        # Ties go to the later date, as the most recent account of the same event.
        day = max(counts, key=lambda d: (counts[d], d))
    assert day is not None
    on_day = [f for f in dated if f.event_date == day]
    return max(
        on_day,
        key=lambda f: (_quote_shows(f, day), f.origin is Origin.CODE, f.significance),
    )


def _quote_shows(fact: Fact, day: date) -> bool:
    return any(
        mention.precision is DatePrecision.DAY and mention.on == day
        for mention in find_dates(fact.quote or "")
    )
