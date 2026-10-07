"""Which shown value a figure in a sentence is about, read from the words around it.

A figure that matches nothing may still be about a subject the link shows ("your
bills total ..."). The clause around it is read first, then the whole sentence when
no other figure of its kind shares it, for the cue words each shown value carries.
"""

import re

from app.services.known_values import KnownValue
from app.services.money_mentions import AmountMention
from app.services.text_mentions import DateMention

Mention = AmountMention | DateMention


def same_subject(
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
            (sum(plain(cue) in context for cue in known.cues), known)
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


def contexts_around(
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
    clause = plain(text[begin:finish])
    if sum(type(m) is type(mention) for m in within) > 1:
        return (clause,)
    return clause, plain(text[start:end])


def plain(text: str) -> str:
    """Lower case with hyphens as spaces, so "Per-person" finds the cue "per person"."""
    return text.lower().replace("-", " ")
