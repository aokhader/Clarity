"""Check the amounts and dates in a piece of text against the fact store, in code.

`check_text` is the matcher, and it knows nothing about shares: it takes the values the
reader may be told (`shown`) and the values they must not be (`withheld`). Each amount
and date in the text gets one verdict:

- supported: a shown value matches it, at the precision it was written;
- do_not_send: only a withheld value matches it;
- differs: no value matches, but one shown value is clearly about the same subject
  (the sentence names it), so that value is offered in its place;
- not_in_file: nothing matches.

A do_not_send verdict returns the rule that withholds the value and the refs of the
facts it matched, so the attorney can open why a sentence is locked (D17). These
routes are firm-only; nothing here reaches a provider. `check_share_draft` applies the
matcher to a provider's link. No model is called.
"""

import re
from collections.abc import Iterable
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Fact, Share
from app.schemas import (
    DraftCheckOut,
    DraftMentionOut,
    DraftSentenceOut,
    MentionVerdict,
    SentenceVerdict,
)
from app.services.fact_views import fact_ref
from app.services.known_values import KnownValue
from app.services.share_values import shown_values, withheld_values
from app.services.text_mentions import (
    AmountMention,
    DateMention,
    DatePrecision,
    find_amounts,
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
    mentions: list[Mention] = sorted(
        [*find_amounts(text), *find_dates(text)], key=lambda m: m.start
    )
    sentences = []
    for start, end in sentence_spans(text):
        within = [m for m in mentions if start <= m.start < end]
        checked = [
            _check(
                text,
                mention,
                _contexts(text, start, end, mention, within),
                shown,
                withheld,
            )
            for mention in within
        ]
        sentences.append(
            DraftSentenceOut(
                start=_utf16(text, start),
                end=_utf16(text, end),
                text=text[start:end],
                verdict=worst_verdict(m.verdict for m in checked),
                mentions=checked,
            )
        )
    return DraftCheckOut(
        verdict=worst_verdict(s.verdict for s in sentences), sentences=sentences
    )


def check_share_draft(
    session: Session, share: Share, text: str, now: datetime
) -> DraftCheckOut:
    """Check text meant for the provider holding `share`. Raises ShareGone if it is not live."""
    return check_text(
        text, shown_values(session, share, now), withheld_values(session, share, now)
    )


def _check(
    text: str,
    mention: Mention,
    contexts: tuple[str, ...],
    shown: list[KnownValue],
    withheld: list[KnownValue],
) -> DraftMentionOut:
    def out(
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

    if matches := [k for k in shown if _matches(mention, k)]:
        return out(
            "supported",
            f"Matches {matches[0].what}",
            (f for k in matches for f in k.facts),
        )
    if blocked := [k for k in withheld if _matches(mention, k)]:
        # The most severe rule is the reason; every matched fact is cited (D17).
        return out(
            "do_not_send",
            min(blocked, key=lambda k: k.rank).what,
            (f for k in blocked for f in k.facts),
        )
    if same := _same_subject(mention, contexts, shown):
        return out(
            "differs",
            f"Differs from {same[0].what}",
            (f for k in same for f in k.facts),
            same[0],
        )
    return out("not_in_file", "Not found in the file")


def _matches(mention: Mention, known: KnownValue) -> bool:
    if isinstance(mention, AmountMention):
        return known.amount_cents is not None and mention.matches(known.amount_cents)
    if known.on is None:
        return False
    if known.month_only:
        # A month on file supports a month written, never a day it does not show.
        return mention.precision is DatePrecision.MONTH and mention.matches(known.on)
    return mention.matches(known.on)


def _same_subject(
    mention: Mention, contexts: tuple[str, ...], shown: list[KnownValue]
) -> list[KnownValue]:
    """The shown value the mention is about, when exactly one value fits best.

    The clause around the mention is read first, so "bills of $X and a limit of $Y"
    ties neither figure to the other's subject.
    """
    is_amount = isinstance(mention, AmountMention)
    candidates = [
        known
        for known in shown
        if known.cues
        and not known.month_only
        and (known.amount_cents is not None if is_amount else known.on is not None)
    ]
    for context in contexts:
        scored = [
            (sum(_plain(cue) in context for cue in known.cues), known)
            for known in candidates
        ]
        best = max((score for score, _ in scored), default=0)
        top = [known for score, known in scored if score == best]
        if best > 0 and len({(k.amount_cents, k.on) for k in top}) == 1:
            return top
    return []


# Where one clause of a sentence ends: punctuation, a dash, or a joining word. A comma
# counts only before a space, so "$1,234" stays whole.
_CLAUSE_BREAK = re.compile(
    r"[;:()—]|,\s|\s-\s|\s(?:and|but|while|whereas|plus)\s", re.IGNORECASE
)


def _contexts(
    text: str, start: int, end: int, mention: Mention, within: list[Mention]
) -> tuple[str, ...]:
    """Where to look for the mention's subject, in plain form: its clause, then the
    whole sentence, but only when no other figure of its kind shares the sentence."""
    begin, finish = start, end
    for brk in _CLAUSE_BREAK.finditer(text, start, end):
        if brk.end() <= mention.start:
            begin = brk.end()
        elif brk.start() >= mention.end:
            finish = brk.start()
            break
    clause = _plain(text[begin:finish])
    if sum(type(m) is type(mention) for m in within) > 1:
        return (clause,)
    return clause, _plain(text[start:end])


def worst_verdict(verdicts: Iterable[SentenceVerdict]) -> SentenceVerdict:
    return min(verdicts, key=_SEVERITY.index, default="unchecked")


def _plain(text: str) -> str:
    """Lower case with hyphens as spaces, so "Per-person" finds the cue "per person"."""
    return text.lower().replace("-", " ")


def _utf16(text: str, index: int) -> int:
    """A Python string index as a JavaScript one: astral characters count twice."""
    return index + sum(1 for ch in text[:index] if ord(ch) > 0xFFFF)
