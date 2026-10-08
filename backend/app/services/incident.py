"""The facts behind the header's date of incident and its account of what happened.

A matter can hold hundreds of incident facts, most read from documents that describe
the collision without dating it. The header cites one, and its chip must open a source
that shows the date. So the firm's own date-of-incident field in Clio (mapped in code)
decides the date when it is set; otherwise the date most facts state does. Among the
facts on that date, one whose quote writes the date out is cited first.

The field fact dates the incident but cannot describe it: its title is the field's
label and its payload is empty. The account of what happened comes from a record the
model read on the same day.
"""

from collections import Counter
from datetime import date

from app.models import Fact, Origin
from app.schemas import IncidentPayload
from app.services.text_mentions import DatePrecision, find_dates


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


def incident_account(facts: list[Fact]) -> Fact | None:
    """The model-read fact that best tells what happened on the header's incident day.

    One with a description leads, then the most significant; the lowest id breaks a
    tie so the choice is stable. Never the field fact: None when no record read on
    that day describes the incident.
    """
    day = _incident_day([f for f in facts if f.event_date is not None])
    told = [f for f in facts if f.event_date == day and f.origin is Origin.MODEL]
    if day is None or not told:
        return None
    return max(told, key=lambda f: (bool(_description(f)), f.significance, -f.id))


def account_text(fact: Fact) -> str:
    """The incident as the record describes it, else the fact's title."""
    return _description(fact) or fact.title


def _description(fact: Fact) -> str | None:
    description = IncidentPayload.model_validate(fact.value_json).description
    return description.strip() if description and description.strip() else None


def _quote_shows(fact: Fact, day: date) -> bool:
    return any(
        mention.precision is DatePrecision.DAY and mention.on == day
        for mention in find_dates(fact.quote or "")
    )
