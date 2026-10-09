"""What the chatbot is shown for one question (D49), chosen in code.

Four parts, in the order the model reads them after what the user pointed at:

- **Overview:** the header's stage, the incident and its account, the facts behind the
  KPI tiles, and the stored brief's sentences with their ids.
- **Retrieved facts:** the matter's renderable facts ranked for the question by
  `rank_facts`, restatements folded, `CHAT_CONTEXT_FACTS` at most.
- **Pages:** excerpts of the pages the attached and the top retrieved facts were read
  from, `CHAT_CONTEXT_PAGES` in all, the attached items' first.
- **History:** the thread's last `CHAT_HISTORY_TURNS` turns, as they are shown.

No model is called here; the ranker is word matching, so `GET /search` uses it too.
"""

import re
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.digest.chat import AttachedItem, ChatInput, PageExcerpt, PriorTurn
from app.models import ChatStatus, ChatTurn, Fact, FactKind
from app.schemas import FactOut
from app.services import brief_view
from app.services.chat_attachments import ResolvedItem
from app.services.chat_pages import page_excerpts
from app.services.fact_views import renderable_facts, with_restatements
from app.services.incident import incident_account, incident_fact
from app.services.kpis import kpi_tiles
from app.services.matter_queries import matter_stage
from app.services.restatements import group_restatements, one_per_record

# Weights of the ranker: a question word at a word start in a fact's title, in its
# quote, and a word that names the fact's kind. Significance (0-100) adds up to 2, so
# it orders facts the words leave tied.
TITLE_WEIGHT = 3
QUOTE_WEIGHT = 1
KIND_WEIGHT = 4
SIGNIFICANCE_DIVISOR = 50
# How many candidates are read per retrieved fact to fold restatements.
CANDIDATES_PER_FACT = 3
# The same for a search row, as the ranked feed reads them (matter_queries.py).
SEARCH_CANDIDATES_PER_ROW = 10
# Facts per KPI tile in the overview; a tile can rest on every bill in the file, and the
# model also receives the computed figures with their fact ids.
OVERVIEW_FACTS_PER_TILE = 12
# Records that restate the incident account, besides its leading fact.
OVERVIEW_INCIDENT_RESTATEMENTS = 2

_WORD = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
# Words a question is made of that say nothing of its subject. "Case" and "file" are
# here because every question is about the case file.
_STOP_WORDS = frozenset(
    {"a", "about", "all", "an", "and", "any", "are", "as", "at", "be", "been", "by"}
    | {"can", "case", "could", "did", "do", "does", "far", "file", "for", "from"}
    | {"give", "had", "has", "have", "how", "i", "if", "in", "into", "is", "it", "its"}
    | {"list", "many", "me", "much", "my", "no", "not", "of", "on", "or", "our", "out"}
    | {"say", "says", "show", "so", "tell", "than", "that", "the", "their", "them"}
    | {"then", "there", "these", "they", "this", "those", "to", "up", "us", "was"}
    | {"we", "were", "what", "what's", "when", "where", "which", "who", "why", "will"}
    | {"with", "would", "yet", "you", "your"}
)
# Generic words that ask about a kind of fact, matched at the start of a question word
# ("bills" and "billed" both find "bill"). No word here comes from any matter.
_KIND_CUES: dict[str, tuple[FactKind, ...]] = {
    "bill": (FactKind.MEDICAL_BILL,),
    "charge": (FactKind.MEDICAL_BILL,),
    "invoice": (FactKind.MEDICAL_BILL,),
    "lien": (FactKind.LIEN,),
    "special": (FactKind.MEDICAL_SPECIALS,),
    "limit": (FactKind.POLICY_LIMIT,),
    "polic": (FactKind.POLICY_LIMIT, FactKind.COVERAGE),
    "insur": (FactKind.COVERAGE, FactKind.POLICY_LIMIT),
    "coverage": (FactKind.COVERAGE, FactKind.POLICY_LIMIT),
    "valu": (FactKind.CASE_VALUE,),
    "worth": (FactKind.CASE_VALUE,),
    "demand": (FactKind.DEMAND,),
    "offer": (FactKind.OFFER,),
    "settle": (FactKind.SETTLEMENT, FactKind.OFFER),
    "negotiat": (FactKind.DEMAND, FactKind.OFFER),
    "injur": (FactKind.INJURY, FactKind.DIAGNOSIS),
    "hurt": (FactKind.INJURY,),
    "pain": (FactKind.INJURY, FactKind.DIAGNOSIS),
    "diagnos": (FactKind.DIAGNOSIS,),
    "treat": (FactKind.TREATMENT_VISIT,),
    "visit": (FactKind.TREATMENT_VISIT,),
    "therap": (FactKind.TREATMENT_VISIT,),
    "appointment": (FactKind.TREATMENT_VISIT,),
    "doctor": (FactKind.TREATMENT_VISIT, FactKind.DIAGNOSIS),
    "surg": (FactKind.TREATMENT_VISIT, FactKind.DIAGNOSIS),
    "record": (FactKind.RECORDS_RECEIVED, FactKind.RECORD_REQUEST),
    "request": (FactKind.RECORD_REQUEST,),
    "liab": (FactKind.LIABILITY,),
    "fault": (FactKind.LIABILITY,),
    "expense": (FactKind.EXPENSE,),
    "cost": (FactKind.EXPENSE,),
    "spen": (FactKind.EXPENSE,),
    "fee": (FactKind.EXPENSE,),
    "deadline": (FactKind.DEADLINE,),
    "statute": (FactKind.DEADLINE,),
    "due": (FactKind.DEADLINE, FactKind.TASK),
    "overdue": (FactKind.DEADLINE, FactKind.TASK),
    "task": (FactKind.TASK,),
    "follow": (FactKind.TASK, FactKind.CALL_NOTE),
    "contact": (FactKind.CLIENT_CONTACT,),
    "call": (FactKind.CALL_NOTE, FactKind.CLIENT_CONTACT),
    "spoke": (FactKind.CLIENT_CONTACT, FactKind.CALL_NOTE),
    "court": (FactKind.LITIGATION_EVENT,),
    "suit": (FactKind.LITIGATION_EVENT,),
    "lawsuit": (FactKind.LITIGATION_EVENT,),
    "litigat": (FactKind.LITIGATION_EVENT,),
    "complaint": (FactKind.LITIGATION_EVENT,),
    "filed": (FactKind.LITIGATION_EVENT,),
    "filing": (FactKind.LITIGATION_EVENT,),
    "dismiss": (FactKind.LITIGATION_EVENT,),
    "hearing": (FactKind.LITIGATION_EVENT,),
    "depos": (FactKind.LITIGATION_EVENT,),
    "trial": (FactKind.LITIGATION_EVENT,),
    "motion": (FactKind.LITIGATION_EVENT,),
    "stage": (FactKind.CASE_STAGE, FactKind.STATUS_CHANGE),
    "status": (FactKind.CASE_STAGE, FactKind.STATUS_CHANGE),
    "accident": (FactKind.INCIDENT,),
    "collision": (FactKind.INCIDENT,),
    "crash": (FactKind.INCIDENT,),
    "incident": (FactKind.INCIDENT,),
    "happen": (FactKind.INCIDENT,),
    "damage": (FactKind.ECONOMIC_DAMAGES,),
    "wage": (FactKind.ECONOMIC_DAMAGES,),
    "cap": (FactKind.RECOVERY_CAP,),
    "party": (FactKind.PARTY,),
    "parties": (FactKind.PARTY,),
}


def query_words(query: str) -> list[str]:
    """The question's words that may name its subject, in order, each once."""
    words = [w for w in _WORD.findall(query.lower()) if w not in _STOP_WORDS]
    return list(dict.fromkeys(words))


def rank_facts(
    facts: list[Fact], query: str, *, matching_only: bool = False
) -> list[Fact]:
    """`facts` ordered for the question, best first.

    A question word scores where it starts a word in the fact's title (x3) or quote
    (x1), so "lien" finds liens but not "client". A word that names the fact's kind
    adds 4, and significance / 50 orders the rest. With `matching_only` (search), only
    facts holding every word at a word start are kept.
    """
    words = query_words(query)
    if matching_only and not words:
        # A search made only of common words still matches them as typed.
        words = list(dict.fromkeys(_WORD.findall(query.lower())))
        if not words:
            return []
    starts = [re.compile(rf"\b{re.escape(w)}", re.IGNORECASE) for w in words]
    cued = {
        kind
        for w in words
        for cue, kinds in _KIND_CUES.items()
        if w.startswith(cue)
        for kind in kinds
    }
    scored: list[tuple[float, Fact]] = []
    for fact in facts:
        quote = fact.quote or ""
        in_title = [bool(p.search(fact.title)) for p in starts]
        in_quote = [bool(p.search(quote)) for p in starts]
        if matching_only and not all(
            t or q for t, q in zip(in_title, in_quote, strict=True)
        ):
            continue
        score = (
            TITLE_WEIGHT * sum(in_title)
            + QUOTE_WEIGHT * sum(in_quote)
            + (KIND_WEIGHT if fact.kind in cued else 0)
            + fact.significance / SIGNIFICANCE_DIVISOR
        )
        scored.append((score, fact))
    scored.sort(
        key=lambda pair: (
            -pair[0],
            -(pair[1].event_date or date.min).toordinal(),
            pair[1].id,
        )
    )
    return [fact for _, fact in scored]


def search_facts(session: Session, matter_id: int, q: str, limit: int) -> list[FactOut]:
    """The Ask bar's instant search: renderable facts holding every word of `q` at a
    word start, ranked like the chatbot's retrieval, one row per restatement group."""
    ranked = rank_facts(
        list(session.scalars(renderable_facts(matter_id))), q, matching_only=True
    )
    groups = group_restatements(ranked[: limit * SEARCH_CANDIDATES_PER_ROW])
    return [with_restatements(group) for group in groups[:limit]]


def build_context(
    session: Session,
    matter_id: int,
    question: str,
    items: list[ResolvedItem],
    history: list[PriorTurn],
    *,
    renderable: dict[int, Fact],
) -> ChatInput:
    settings = get_settings()
    shown = list(renderable.values())
    overview, brief_sentences = _overview(session, matter_id, renderable)

    # Attached items' pages come first and count against the one page budget.
    kept = _round_robin([item.pages for item in items], settings.chat_context_pages)
    attached = [
        AttachedItem(label=item.label, facts=item.facts, pages=pages)
        for item, pages in zip(items, kept, strict=True)
    ]
    seen_pages = {(p.source_id, p.page_no) for pages in kept for p in pages}
    budget = settings.chat_context_pages - len(seen_pages)

    known = {f.id for item in items for f in item.facts} | {f.id for f in overview}
    candidates = [f for f in rank_facts(shown, question) if f.id not in known]
    retrieved = _folded(candidates, settings.chat_context_facts)
    # Read enough excerpts to skip the pages an item already carries.
    excerpts = page_excerpts(
        session, retrieved, shown, settings.chat_page_chars, budget + len(seen_pages)
    )
    pages = [p for p in excerpts if (p.source_id, p.page_no) not in seen_pages]
    pages = pages[:budget]
    return ChatInput(
        overview=overview,
        brief_sentences=brief_sentences,
        attached=attached,
        retrieved=retrieved,
        pages=pages,
        history=history,
    )


def context_fact_ids(chat_input: ChatInput) -> list[int]:
    """Every fact id the model is shown, for the turn's audit trail."""
    ids = [f.id for item in chat_input.attached for f in item.facts]
    ids += [f.id for f in chat_input.overview]
    ids += [i for _, cited in chat_input.brief_sentences for i in cited]
    ids += [f.id for f in chat_input.retrieved]
    pages: list[PageExcerpt] = [p for a in chat_input.attached for p in a.pages]
    ids += [i for p in [*pages, *chat_input.pages] for i in p.fact_ids]
    return sorted(set(ids))


def prior_turns(
    session: Session, turn: ChatTurn, renderable: dict[int, Fact]
) -> list[PriorTurn]:
    """The thread's turns before `turn`, the last CHAT_HISTORY_TURNS, oldest first. A
    done turn's answer is what is shown of it today; any other turn's is empty."""
    limit = get_settings().chat_history_turns
    if limit <= 0:
        return []
    earlier = session.scalars(
        select(ChatTurn)
        .where(ChatTurn.thread_id == turn.thread_id, ChatTurn.id < turn.id)
        .order_by(ChatTurn.id.desc())
        .limit(limit)
    ).all()
    return [
        PriorTurn(question=t.question, answer=shown_answer(t, renderable))
        for t in reversed(earlier)
    ]


def shown_answer(turn: ChatTurn, renderable: dict[int, Fact]) -> str:
    """A done turn's sentences that are still shown, joined; "" for any other turn."""
    if turn.status is not ChatStatus.DONE or not turn.answer_json:
        return ""
    return " ".join(
        s["text"]
        for s in turn.answer_json.get("sentences", [])
        if all(i in renderable for i in s.get("fact_ids", []))
    )


def _overview(
    session: Session, matter_id: int, renderable: dict[int, Fact]
) -> tuple[list[Fact], list[tuple[str, list[int]]]]:
    by_kind: dict[FactKind, list[Fact]] = {kind: [] for kind in FactKind}
    for fact in renderable.values():
        by_kind[fact.kind].append(fact)
    stage = matter_stage(session, matter_id)
    facts = [renderable[r.id] for r in stage.facts if r.id in renderable]
    incident = incident_fact(by_kind[FactKind.INCIDENT])
    if incident is not None:
        facts.append(incident)
    account = one_per_record(incident_account(by_kind[FactKind.INCIDENT]))
    facts += account[: 1 + OVERVIEW_INCIDENT_RESTATEMENTS]
    for tile in kpi_tiles(by_kind):
        ids = dict.fromkeys(r.id for value in tile.values for r in value.facts)
        facts += [
            renderable[i]
            for i in list(ids)[:OVERVIEW_FACTS_PER_TILE]
            if i in renderable
        ]

    try:
        brief = brief_view.matter_brief(session, matter_id)
    except brief_view.BriefNotFound:
        brief = None
    sentences: list[tuple[str, list[int]]] = []
    if brief is not None:
        # The brief as the page shows it: a sentence citing a fact that can no longer
        # be shown is already left out.
        if brief.headline_facts:
            sentences.append((brief.headline, [r.id for r in brief.headline_facts]))
        sentences += [(s.text, [r.id for r in s.facts]) for s in brief.sentences]
        facts += [renderable[i] for _, ids in sentences for i in ids if i in renderable]
    return list({f.id: f for f in facts}.values()), sentences


def _folded(ranked: list[Fact], limit: int) -> list[Fact]:
    """The best `limit` facts with restatements folded: one fact per finding, so forty
    records restating one account do not fill the context. The window of candidates
    widens until it holds `limit` findings or every fact."""
    if limit <= 0:
        return []
    window = limit * CANDIDATES_PER_FACT
    while True:
        groups = group_restatements(ranked[:window])
        if len(groups) >= limit or window >= len(ranked):
            return [group[0] for group in groups[:limit]]
        window *= 2


def _round_robin(
    pages_by_item: list[list[PageExcerpt]], limit: int
) -> list[list[PageExcerpt]]:
    """Up to `limit` pages over all items, each item's first page before any item's
    second, so one long record cannot crowd out another item's page."""
    kept: list[list[PageExcerpt]] = [[] for _ in pages_by_item]
    taken: set[tuple[int, int | None]] = set()
    depth = 0
    while len(taken) < limit and any(depth < len(p) for p in pages_by_item):
        for index, pages in enumerate(pages_by_item):
            if depth < len(pages) and len(taken) < limit:
                page = pages[depth]
                if (page.source_id, page.page_no) not in taken:
                    taken.add((page.source_id, page.page_no))
                    kept[index].append(page)
        depth += 1
    return kept
