"""Facts that state the same thing from different records, grouped so each shows once.

Extraction reads every record on its own, so one finding comes back once per note,
email and page that mentions it. Two facts are restatements when they are of one kind
and:

- for a standing figure (a limit, a valuation, a damages total), state the same figure,
  whenever and wherever it was written;
- for anything else, fall on the same day (or are both undated) and say nearly the
  same thing: most of their title words are shared.

Like events on different days (two therapy sessions) are never merged.
"""

import re
from typing import Any

from app.models import Fact, FactKind

_STANDING_FIGURES = {
    FactKind.POLICY_LIMIT,
    FactKind.CASE_VALUE,
    FactKind.MEDICAL_SPECIALS,
    FactKind.ECONOMIC_DAMAGES,
    FactKind.RECOVERY_CAP,
}
_FIGURE_KEYS = ("amount_cents", "low_cents", "high_cents", "per", "policy")
# Share of title words two facts must have in common to say the same thing.
SAME_WORDS = 0.6
_FILLER = frozenset(
    {"a", "an", "and", "as", "at", "by", "for", "from", "in", "is", "of", "on", "or"}
    | {"the", "to", "was", "were", "with"}
)


def group_restatements(facts: list[Fact]) -> list[list[Fact]]:
    """Restatements together, in the order given; each group's first fact leads it."""
    groups: list[list[Fact]] = []
    for fact in facts:
        group = next((g for g in groups if _restates(fact, g[0])), None)
        if group is None:
            groups.append([fact])
        else:
            group.append(fact)
    return groups


def one_per_record(group: list[Fact]) -> list[Fact]:
    """The group with one fact per source record, the first in the group's order, so
    a document that states a finding on many pages counts once."""
    seen: set[int] = set()
    kept = []
    for fact in group:
        if fact.source_id not in seen:
            seen.add(fact.source_id)
            kept.append(fact)
    return kept


def restates_across_kinds(fact: Fact, other: Fact) -> bool:
    """Whether two facts say the same thing whatever their kinds and dates: most of
    their title words are shared. For an undated fact that another record files under
    another kind with a date (D43)."""
    return _same_words(fact.title, other.title)


def _restates(fact: Fact, lead: Fact) -> bool:
    if fact.kind is not lead.kind:
        return False
    figure = _figure(fact)
    if fact.kind in _STANDING_FIGURES and figure is not None:
        return figure == _figure(lead)
    return fact.event_date == lead.event_date and _same_words(fact.title, lead.title)


def _figure(fact: Fact) -> tuple[Any, ...] | None:
    """The figure a fact states, or None when it carries no amount."""
    value = fact.value_json or {}
    figure = tuple(value.get(key) for key in _FIGURE_KEYS)
    return figure if any(isinstance(v, int) for v in figure) else None


def _words(title: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", title.lower())) - _FILLER


def _same_words(one: str, other: str) -> bool:
    a, b = _words(one), _words(other)
    return bool(a | b) and len(a & b) / len(a | b) >= SAME_WORDS
