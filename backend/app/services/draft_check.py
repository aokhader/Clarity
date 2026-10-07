"""Check the amounts and dates in a piece of text against the fact store, in code.

`check_text` is the matcher, and it knows nothing about shares: it takes the values the
reader may be told (`shown`) and the values they must not be (`withheld`). Each amount
and date in the text gets one verdict:

- supported: a shown value matches it, at the precision it was written;
- do_not_send: only a withheld value matches it;
- differs: no value matches, but one shown value is clearly about the same subject
  (the sentence names it), so that value is offered in its place;
- not_in_file: nothing matches.

A do_not_send verdict returns the withheld value's reason and nothing else, so a
check never reveals what it guards. `check_share_draft` applies the matcher to a
provider's link. No model is called.
"""

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
        sentence = _plain(text[start:end])
        checked = [
            _check(text, mention, sentence, shown, withheld)
            for mention in mentions
            if start <= mention.start < end
        ]
        sentences.append(
            DraftSentenceOut(
                start=_utf16(text, start),
                end=_utf16(text, end),
                text=text[start:end],
                verdict=_worst(m.verdict for m in checked),
                mentions=checked,
            )
        )
    return DraftCheckOut(
        verdict=_worst(s.verdict for s in sentences), sentences=sentences
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
    sentence: str,
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
        # The reason names the rule; the matched value and its facts stay here.
        return out("do_not_send", min(blocked, key=lambda k: k.rank).what)
    if same := _same_subject(mention, sentence, shown):
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
    mention: Mention, sentence: str, shown: list[KnownValue]
) -> list[KnownValue]:
    """The shown value this sentence is about, when exactly one value fits best."""
    is_amount = isinstance(mention, AmountMention)
    scored = [
        (sum(_plain(cue) in sentence for cue in known.cues), known)
        for known in shown
        if not known.month_only
        and (known.amount_cents is not None if is_amount else known.on is not None)
    ]
    best = max((score for score, _ in scored), default=0)
    top = [known for score, known in scored if score == best]
    if best == 0 or len({(k.amount_cents, k.on) for k in top}) != 1:
        return []
    return top


def _worst(verdicts: Iterable[SentenceVerdict]) -> SentenceVerdict:
    return min(verdicts, key=_SEVERITY.index, default="unchecked")


def _plain(text: str) -> str:
    """Lower case with hyphens as spaces, so "Per-person" finds the cue "per person"."""
    return text.lower().replace("-", " ")


def _utf16(text: str, index: int) -> int:
    """A Python string index as a JavaScript one: astral characters count twice."""
    return index + sum(1 for ch in text[:index] if ord(ch) > 0xFFFF)
