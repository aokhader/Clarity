"""Check the amounts and dates in a piece of text against the fact store, in code.

`check_text` is the matcher, and it knows nothing about shares: it takes the values the
reader may be told (`shown`) and the values they must not be (`withheld`). Each amount
and date in the text gets one verdict (D25):

- supported: a shown value matches it, at the precision it was written;
- do_not_send: it discloses a withheld value. An amount locks when it equals one,
  when it is that value rounded the way the writer may have rounded it ("$330,000"),
  when a range around it brackets one, or when two amounts in the text add up to one.
  A date locks only when it is the date of a sensitive internal fact (an offer, a
  demand, a settlement, a valuation, a limit) or of a legal deadline, by its type
  (D28): a plain calendar entry does not lock. $0 never locks;
- differs: no value matches, but one shown value is clearly about the same subject
  (the sentence names it), so that value is offered in its place;
- not_in_file: nothing matches.

A number with no money marker (bare digits, or words) is reported only when it is
supported or locks: on its own it may be a year or a reference number. A date is compared
at the precision written, so a month and year never matches a day.

A do_not_send verdict returns the rule that withholds the value and the refs of the
facts it matched, so the attorney can open why a sentence is locked (D17). These
routes are firm-only; nothing here reaches a provider. No model is called.
"""

from collections.abc import Iterable
from itertools import combinations

from app.models import Fact
from app.schemas import (
    DraftCheckOut,
    DraftMentionOut,
    DraftSentenceOut,
    MentionVerdict,
    SentenceVerdict,
)
from app.services.date_sensitivity import sensitive_date
from app.services.fact_views import fact_ref
from app.services.known_values import KnownValue
from app.services.money_mentions import (
    ROUNDING_FROM_CENTS,
    AmountMention,
    find_amounts,
    find_ranges,
)
from app.services.subject_cues import contexts_around, same_subject
from app.services.text_mentions import (
    DateMention,
    DatePrecision,
    find_dates,
    sentence_spans,
)

Mention = AmountMention | DateMention

# Worst first: a sentence takes the verdict of its worst mention.
_SEVERITY: list[SentenceVerdict] = [
    "do_not_send",
    "differs",
    "not_in_file",
    "supported",
    "unchecked",
]


def check_text(
    text: str, shown: list[KnownValue], withheld: list[KnownValue]
) -> DraftCheckOut:
    dates = find_dates(text)
    amounts = [
        a
        for a in find_amounts(text)
        if a.marked or not any(a.start < d.end and d.start < a.end for d in dates)
    ]
    mentions: list[Mention] = sorted([*amounts, *dates], key=lambda m: m.start)
    checked: dict[int, DraftMentionOut | None] = {}
    spans = sentence_spans(text)
    for start, end in spans:
        within = [m for m in mentions if start <= m.start < end]
        for mention in within:
            contexts = contexts_around(text, start, end, mention, within)
            checked[id(mention)] = _check(text, mention, contexts, shown, withheld)
    _lock_combined(text, amounts, checked, shown, withheld)
    sentences = []
    for start, end in spans:
        found = [
            out
            for m in mentions
            if start <= m.start < end and (out := checked.get(id(m))) is not None
        ]
        sentences.append(
            DraftSentenceOut(
                start=_utf16(text, start),
                end=_utf16(text, end),
                text=text[start:end],
                verdict=worst_verdict(m.verdict for m in found),
                mentions=found,
            )
        )
    return DraftCheckOut(
        verdict=worst_verdict(s.verdict for s in sentences), sentences=sentences
    )


def _out(
    text: str,
    mention: Mention,
    verdict: MentionVerdict,
    reason: str,
    facts: Iterable[Fact] = (),
    file_value: KnownValue | None = None,
) -> DraftMentionOut:
    return DraftMentionOut(
        start=_utf16(text, mention.start),
        end=_utf16(text, mention.end),
        text=text[mention.start : mention.end],
        kind="amount" if isinstance(mention, AmountMention) else "date",
        verdict=verdict,
        reason=reason,
        facts=[fact_ref(f) for f in {f.id: f for f in facts}.values()],
        file_amount_cents=file_value.amount_cents if file_value else None,
        file_date=file_value.on if file_value else None,
    )


def _locked(text: str, mention: Mention, blocked: list[KnownValue]) -> DraftMentionOut:
    # The most severe rule is the reason; every matched fact is cited (D17).
    return _out(
        text,
        mention,
        "do_not_send",
        min(blocked, key=lambda k: k.rank).what,
        (f for k in blocked for f in k.facts),
    )


def _check(
    text: str,
    mention: Mention,
    contexts: tuple[str, ...],
    shown: list[KnownValue],
    withheld: list[KnownValue],
) -> DraftMentionOut | None:
    if isinstance(mention, AmountMention):
        matches = [
            k
            for k in shown
            if k.amount_cents is not None and mention.matches(k.amount_cents)
        ]
        blocked = _amount_locks(mention, shown, withheld)
    else:
        matches = [k for k in shown if _date_matches(mention, k)]
        blocked = [
            k
            for k in withheld
            if _date_matches(mention, k) and any(sensitive_date(f) for f in k.facts)
        ]
    if matches:
        return _out(
            text,
            mention,
            "supported",
            f"Matches {matches[0].what}",
            (f for k in matches for f in k.facts),
        )
    if blocked:
        return _locked(text, mention, blocked)
    if isinstance(mention, AmountMention) and not mention.marked:
        return None  # a bare number that matches nothing may be a year or an id
    if same := same_subject(mention, contexts, shown):
        return _out(
            text,
            mention,
            "differs",
            f"Differs from {same[0].what}",
            (f for k in same for f in k.facts),
            same[0],
        )
    return _out(text, mention, "not_in_file", "Not found in the file")


def _amount(known: KnownValue) -> int:
    """The known value's amount, or 0 when it has none. $0 never locks."""
    return known.amount_cents or 0


def _amount_locks(
    mention: AmountMention, shown: list[KnownValue], withheld: list[KnownValue]
) -> list[KnownValue]:
    """Withheld values the amount equals, or is a rounding of."""
    if mention.cents == 0:
        return []
    exact = [k for k in withheld if _amount(k) and mention.matches(_amount(k))]
    if exact or not mention.marked:
        return exact
    # A rounded figure that may be the provider's own (shown) figure is not a leak.
    if any(_amount(k) and mention.rounds_from(_amount(k)) for k in shown):
        return []
    return [
        k
        for k in withheld
        if not k.exact_only and _amount(k) and mention.rounds_from(_amount(k))
    ]


def _lock_combined(
    text: str,
    amounts: list[AmountMention],
    checked: dict[int, DraftMentionOut | None],
    shown: list[KnownValue],
    withheld: list[KnownValue],
) -> None:
    """Lock amounts that disclose a withheld figure together: a range around it, or two
    amounts that add up to it. Neither may be a figure the link already shows."""
    internal = [k for k in withheld if not k.exact_only and _amount(k)]
    shown_amounts = [_amount(k) for k in shown if _amount(k)]

    def open_to_lock(mention: AmountMention) -> bool:
        out = checked.get(id(mention))
        return out is None or out.verdict not in ("supported", "do_not_send")

    for found in find_ranges(text, amounts):
        if any(found.brackets(cents) for cents in shown_amounts):
            continue
        if blocked := [k for k in internal if found.brackets(_amount(k))]:
            for end in (found.low, found.high):
                checked[id(end)] = _locked(text, end, blocked)
    for one, other in combinations(amounts, 2):
        total = one.cents + other.cents
        slack = one.tolerance_cents + other.tolerance_cents
        if (
            total < ROUNDING_FROM_CENTS
            or not (one.cents and other.cents)
            or not (open_to_lock(one) and open_to_lock(other))
            or any(abs(total - cents) <= slack for cents in shown_amounts)
        ):
            continue
        if blocked := [k for k in internal if abs(total - _amount(k)) <= slack]:
            for part in (one, other):
                checked[id(part)] = _locked(text, part, blocked)


def _date_matches(mention: DateMention, known: KnownValue) -> bool:
    """At the precision written: a month matches only a month on file, never a day."""
    if known.on is None:
        return False
    if known.month_only or mention.precision is DatePrecision.MONTH:
        return (
            known.month_only
            and mention.precision is DatePrecision.MONTH
            and mention.matches(known.on)
        )
    return mention.matches(known.on)


def worst_verdict(verdicts: Iterable[SentenceVerdict]) -> SentenceVerdict:
    return min(verdicts, key=_SEVERITY.index, default="unchecked")


def _utf16(text: str, index: int) -> int:
    """A Python string index as a JavaScript one: astral characters count twice."""
    return index + sum(1 for ch in text[:index] if ord(ch) > 0xFFFF)
