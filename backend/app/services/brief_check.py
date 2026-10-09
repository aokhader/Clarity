"""The stored brief, checked against today's file each time it is served (D12, D14).

A model writes the brief once; the facts under it keep changing (a corrected bill, a new
sync). So every amount and date in a sentence goes through the draft checker's matcher
(`check_text`) against what the firm page may show: the sentence's own cited facts
first, then every renderable fact, then the totals computed from them. A figure no fact
states, where one value clearly owns the subject ("bills" and today's bills total), is
marked differs with today's value and the facts behind it. Nothing is withheld from
the firm, so no mention is ever do_not_send here.

Dates are also held to the sentence's citations. A sentence that states one day but
cites a record dated otherwise has merged two events (two exams on different days, for
example), so that date differs, offering the other record's date and its facts.
"""

from dataclasses import replace
from datetime import date

from app.models import Fact, FactKind
from app.schemas import DraftMentionOut, ExpensePayload, FactRef, SentenceVerdict
from app.services.bills import count_bills
from app.services.draft_check import check_text, worst_verdict
from app.services.fact_views import fact_ref
from app.services.known_values import KnownValue, fact_values
from app.services.text_mentions import DateMention, DatePrecision, find_dates

# Words that name the subject of a kind's amount, so a sentence's wrong figure for it
# can be set against the file's. A kind left out is never offered as "the file's value".
_CUES_BY_KIND: dict[FactKind, tuple[str, ...]] = {
    FactKind.CASE_VALUE: ("valu", "worth"),
    FactKind.POLICY_LIMIT: ("limit",),
    FactKind.MEDICAL_SPECIALS: ("special",),
    FactKind.DEMAND: ("demand",),
    FactKind.OFFER: ("offer",),
    FactKind.SETTLEMENT: ("settle",),
    FactKind.LIEN: ("lien",),
}
_BILL_CUES = ("bill", "medical", "charge")
_SPEND_CUES = ("expense", "cost", "spent", "spend")


def file_values(facts: list[Fact]) -> list[KnownValue]:
    """Every amount and date the firm page may show, and today's computed totals."""
    values = [
        replace(value, cues=_CUES_BY_KIND.get(fact.kind, ()))
        for fact in facts
        for value in fact_values(fact, "a fact in the file")
    ]
    counted = count_bills([f for f in facts if f.kind is FactKind.MEDICAL_BILL])
    if counted:
        values.append(
            KnownValue(
                "today's medical bills total",
                amount_cents=sum(c.total_cents for c in counted),
                facts=tuple(f for c in counted for f in c.facts),
                cues=_BILL_CUES,
            )
        )
    values += [
        KnownValue(
            "a provider's bills total today",
            amount_cents=c.total_cents,
            facts=tuple(c.facts),
        )
        for c in counted
        if c.provider_contact_id is not None
    ]
    spent = [
        (f, cents)
        for f in facts
        if f.kind is FactKind.EXPENSE
        and (cents := ExpensePayload.model_validate(f.value_json).amount_cents)
        is not None
    ]
    if spent:
        values.append(
            KnownValue(
                "today's firm spend total",
                amount_cents=sum(cents for _, cents in spent),
                facts=tuple(f for f, _ in spent),
                cues=_SPEND_CUES,
            )
        )
    return with_months(values)


def with_months(values: list[KnownValue]) -> list[KnownValue]:
    """Each dated value also as its month: a brief may say "in July" of a dated event.

    The draft checker compares a month only with a month on file (D25); the brief is
    the firm's own summary, so its months are read against the days they cover."""
    months = [
        replace(v, on=v.on.replace(day=1), month_only=True)
        for v in values
        if v.on is not None and not v.month_only
    ]
    return values + months


def figures_stated_by(
    text: str, facts: list[Fact]
) -> dict[tuple[int, int], list[FactRef]]:
    """Each figure in `text` that one of `facts` states itself, by its offsets, with
    the facts that state it. No computed total takes part, so every fact returned holds
    the figure on its own record."""
    stated = with_months([v for f in facts for v in fact_values(f, "a fact")])
    checked = check_text(text, stated, [])
    return {
        (m.start, m.end): m.facts
        for s in checked.sentences
        for m in s.mentions
        if m.verdict == "supported"
    }


def check_sentence(
    text: str, cited: list[Fact], file: list[KnownValue]
) -> tuple[SentenceVerdict, list[DraftMentionOut]]:
    """One brief sentence (or the headline): its verdict and every mention's."""
    own = with_months(
        [v for f in cited for v in fact_values(f, "a fact this sentence cites")]
    )
    checked = check_text(text, [*own, *file], [])
    mentions = [m for s in checked.sentences for m in s.mentions]
    cited_ids = {f.id for f in cited}
    mentions = [_cited_first(m, cited_ids) for m in mentions]
    mentions = _held_to_citations(mentions, cited)
    return worst_verdict(m.verdict for m in mentions), mentions


def _cited_first(mention: DraftMentionOut, cited_ids: set[int]) -> DraftMentionOut:
    """A value the sentence's own citations state needs no other source."""
    own = [ref for ref in mention.facts if ref.id in cited_ids]
    if mention.verdict == "supported" and own:
        return mention.model_copy(update={"facts": own})
    return mention


def _held_to_citations(
    mentions: list[DraftMentionOut], cited: list[Fact]
) -> list[DraftMentionOut]:
    """Day-precision dates against the dates of the facts the sentence cites."""
    dated = [f for f in cited if f.event_date is not None]
    days = {id(m): d for m in mentions if (d := _written_day(m)) is not None}
    out = []
    for mention in mentions:
        day = days.get(id(mention))
        if day is not None and dated:
            if len(days) == 1 and (merged := _other_record(day, cited)):
                mention = _differs(mention, merged, "A cited record is dated otherwise")
            elif mention.verdict == "not_in_file":
                mention = _differs(
                    mention,
                    _nearest(day, dated),
                    "Differs from the dates of the facts it cites",
                )
        out.append(mention)
    return out


def _other_record(day: date, cited: list[Fact]) -> list[Fact]:
    """Cited facts from a record that is dated, but never on `day`."""
    by_source: dict[int, list[Fact]] = {}
    for fact in cited:
        by_source.setdefault(fact.source_id, []).append(fact)
    for facts in by_source.values():
        days = {f.event_date for f in facts if f.event_date is not None}
        if days and day not in days:
            return sorted(facts, key=lambda f: (f.event_date is None, f.event_date))
    return []


def _nearest(day: date, dated: list[Fact]) -> list[Fact]:
    closest = min(dated, key=lambda f: abs((f.event_date or day) - day))
    return [f for f in dated if f.event_date == closest.event_date]


def _written_day(mention: DraftMentionOut) -> date | None:
    """The day a date mention states, or None for a month or a day with no year."""
    if mention.kind != "date":
        return None
    found: list[DateMention] = find_dates(mention.text)
    if not found or found[0].precision is not DatePrecision.DAY:
        return None
    return found[0].on


def _differs(
    mention: DraftMentionOut, facts: list[Fact], reason: str
) -> DraftMentionOut:
    if not facts:
        return mention
    return mention.model_copy(
        update={
            "verdict": "differs",
            "reason": reason,
            "facts": [fact_ref(f) for f in facts],
            "file_amount_cents": None,
            "file_date": facts[0].event_date,
        }
    )
