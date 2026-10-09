"""The plain-text transcript of a closed chat thread (D52), written in code.

It is built once, when the thread closes, from the turns exactly as they were served
then, and stored beside them (`ChatTranscript.text`); the download serves the stored
text. Each source is named as the drawer names it, with its page, so a reader can find
the record again. Nothing here calls a model.
"""

from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.digest.records import display_date
from app.models import ChatThread, Fact
from app.schemas import ChatSentenceOut, ChatTurnOut, DraftMentionOut
from app.services.matter_queries import matter_display_number
from app.services.source_views import source_name

UNKNOWN_USER = "an unknown user"
# Verdicts worth a note after the sentence; "supported" and "unchecked" need none.
_VERDICT_WORDS = {
    "differs": "differs from the file",
    "not_in_file": "not found in the file",
    "not_on_link": "not on the provider link",
    "do_not_send": "internal",
}


def transcript_text(
    session: Session,
    thread: ChatThread,
    turns: list[ChatTurnOut],
    closed_by: str | None,
    closed_at: datetime,
) -> str:
    number = matter_display_number(session, thread.matter_id)
    names = _source_names(
        session, (f.id for t in turns for s in t.sentences for f in s.facts)
    )
    lines = [
        "Clarity: chat transcript",
        f"Matter: {number or f'matter {thread.matter_id}'}",
        f"Thread: {thread.title}",
        f"Closed by {closed_by or UNKNOWN_USER}, {when(closed_at)}",
        "Each answer is as it was served when the thread was closed.",
    ]
    for index, turn in enumerate(turns, start=1):
        lines += ["", *_turn_lines(index, turn, names)]
    return "\n".join(lines) + "\n"


def when(moment: datetime) -> str:
    """Oct 9, 2026, 12:10 PM UTC-07:00: the server's local time, with its offset, since a
    downloaded file has no viewer's time zone to show it in."""
    local = moment.astimezone()
    hour = local.hour % 12 or 12
    noon = "AM" if local.hour < 12 else "PM"
    offset = local.strftime("%z")
    zone = "UTC" if offset in ("", "+0000") else f"UTC{offset[:3]}:{offset[3:]}"
    return f"{display_date(local.date())}, {hour}:{local.minute:02d} {noon} {zone}"


def money(cents: int) -> str:
    """$2,480 for whole dollars, $2,480.50 otherwise, as the app shows money."""
    sign = "-" if cents < 0 else ""
    dollars = Decimal(abs(cents)) / 100
    shown = f"{dollars:,.0f}" if cents % 100 == 0 else f"{dollars:,.2f}"
    return f"{sign}${shown}"


def cost(micros: int | None) -> str:
    """Model spend as the app shows it: $0.42, or "under $0.01" for a sliver."""
    if micros is None:
        return "none"
    if 0 < micros < 10_000:
        return "under $0.01"
    return f"${Decimal(micros) / 1_000_000:,.2f}"


def _turn_lines(index: int, turn: ChatTurnOut, names: dict[int, str]) -> list[str]:
    lines = [
        f"Question {index}, asked by {turn.asked_by or UNKNOWN_USER}, {when(turn.asked_at)}",
        turn.question,
    ]
    if turn.items:
        lines.append("Pointed at: " + "; ".join(item.label for item in turn.items))
    match turn.status:
        case "done":
            answered = f" ({when(turn.answered_at)})" if turn.answered_at else ""
            lines.append(f"Answer{answered}")
            lines += [f"- {_sentence(s, names)}" for s in turn.sentences]
            if not turn.sentences:
                lines.append("- No sentence of the answer could be shown.")
        case "failed":
            lines.append(
                f"No answer: {turn.error or 'the answer could not be written'}"
            )
        case "no_model":
            lines.append("No answer: chat was not configured.")
        case _:
            lines.append("No answer: it was still being written.")
    if turn.withdrawn:
        plural = "sentence" if turn.withdrawn == 1 else "sentences"
        lines.append(
            f"Withdrawn: {turn.withdrawn} {plural}, citing a record that could no longer"
            " be shown."
        )
    lines.append(f"Cost: {cost(turn.cost_micro_usd)}")
    return lines


def _sentence(sentence: ChatSentenceOut, names: dict[int, str]) -> str:
    if sentence.not_in_file:
        return f"{sentence.text} [the file does not say]"
    sources = "; ".join(names.get(f.id, "a record") for f in sentence.facts)
    text = f"{sentence.text} [{sources}]"
    words = _VERDICT_WORDS.get(sentence.verdict)
    if words is None:
        return text
    # The figures behind the verdict, with the file's own where it differs.
    figures = "; ".join(
        _figure(m) for m in sentence.mentions if m.verdict == sentence.verdict
    )
    return f"{text} ({words}{': ' + figures if figures else ''})"


def _figure(mention: DraftMentionOut) -> str:
    if mention.file_amount_cents is not None:
        return f"{mention.text}, the file has {money(mention.file_amount_cents)}"
    if mention.file_date is not None:
        return f"{mention.text}, the file has {display_date(mention.file_date)}"
    return mention.text


def _source_names(session: Session, fact_ids: Iterable[int]) -> dict[int, str]:
    """Each cited fact's source, named as the drawer names it, with the cited page."""
    ids = set(fact_ids)
    if not ids:
        return {}
    facts = session.scalars(
        select(Fact).options(selectinload(Fact.source)).where(Fact.id.in_(ids))
    )
    return {f.id: source_name(f.source, f.page_no) for f in facts}
