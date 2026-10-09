"""The text of the pages the chatbot's facts were read from (D49).

A fact's quote is a sentence or two; the page around it often holds what a question
asks next. So the context carries excerpts of the pages its facts came from: a
document's page text, or a note's, an email's or a call's whole text (page None). Only
a page that holds renderable facts is sent, with those facts' ids, since they are the
only ids the model may cite for it. A scan has no text layer and sends nothing.
"""

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.digest.chat import PageExcerpt
from app.models import Fact, Page, Source, SourceType
from app.services.source_views import source_text

PageKey = tuple[int, int | None]  # (source id, page number or None for a whole record)

# How much of the excerpt comes before a quote that lies past the cut, so the reader
# sees what leads up to it.
_LEAD_IN = 4


def page_excerpts(
    session: Session,
    facts: list[Fact],
    renderable: list[Fact],
    chars: int,
    limit: int,
) -> list[PageExcerpt]:
    """Excerpts of the pages `facts` were read from, in the facts' order, at most
    `limit`, each cut to `chars` around the first quote it holds."""
    on_page: dict[PageKey, list[Fact]] = defaultdict(list)
    for fact in renderable:
        on_page[(fact.source_id, fact.page_no)].append(fact)
    quotes: dict[PageKey, list[str]] = defaultdict(list)
    for fact in facts:
        if fact.quote:
            quotes[(fact.source_id, fact.page_no)].append(fact.quote)
    excerpts: list[PageExcerpt] = []
    for key in dict.fromkeys((f.source_id, f.page_no) for f in facts):
        if len(excerpts) >= limit:
            break
        held = on_page.get(key)
        if not held:
            continue
        text = _page_text(session, key)
        if not text:
            continue
        excerpts.append(
            PageExcerpt(
                source_id=key[0],
                page_no=key[1],
                text=_cut(text, quotes.get(key, []), chars),
                fact_ids=[f.id for f in held],
            )
        )
    return excerpts


def _page_text(session: Session, key: PageKey) -> str | None:
    source_id, page_no = key
    if page_no is None:
        source = session.get(Source, source_id)
        if source is None or source.clio_type is SourceType.DOCUMENT:
            return None
        text = source_text(source)
    else:
        text = session.scalar(
            select(Page.text).where(
                Page.source_id == source_id, Page.page_no == page_no
            )
        )
    return text.strip() if text and text.strip() else None


def _cut(text: str, quotes: list[str], chars: int) -> str:
    """The first `chars` characters, or a window that holds the first quote found
    past them."""
    if len(text) <= chars:
        return text
    for quote in quotes:
        needle = quote.strip()[:80]
        at = text.find(needle) if needle else -1
        if at >= 0 and at + len(quote) > chars:
            start = max(0, min(at - chars // _LEAD_IN, len(text) - chars))
            return text[start : start + chars]
    return text[:chars]
