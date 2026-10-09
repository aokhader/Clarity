"""What the model calls cost, from `llm_calls`, with the chatbot kept apart (D49).

The digest's figures (the README's cost per case, the ops footer) count every purpose
but `chat`, so asking questions never inflates what a matter cost to digest.
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import LlmCall, Page, Source
from app.schemas import CostOut

# The `llm_calls.purpose` of a chat answer (docs/chat-contract.md).
CHAT_PURPOSE = "chat"


def matter_cost(session: Session, matter_id: int) -> CostOut:
    """Tokens and dollars actually paid. Cache hits cost nothing and are counted apart."""
    calls, hits, tokens_in, tokens_out, micro = session.execute(
        select(
            func.count(LlmCall.id).filter(LlmCall.cache_hit.is_(False)),
            func.count(LlmCall.id).filter(LlmCall.cache_hit.is_(True)),
            func.coalesce(func.sum(LlmCall.input_tokens), 0),
            func.coalesce(func.sum(LlmCall.output_tokens), 0),
            func.coalesce(func.sum(LlmCall.cost_micro_usd), 0),
        ).where(LlmCall.matter_id == matter_id, LlmCall.purpose != CHAT_PURPOSE)
    ).one()
    chat_calls, chat_micro = session.execute(
        select(
            func.count(LlmCall.id).filter(LlmCall.cache_hit.is_(False)),
            func.coalesce(func.sum(LlmCall.cost_micro_usd), 0),
        ).where(LlmCall.matter_id == matter_id, LlmCall.purpose == CHAT_PURPOSE)
    ).one()
    pages = session.scalar(
        select(func.count(Page.id)).join(Source).where(Source.matter_id == matter_id)
    )
    return CostOut(
        matter_id=matter_id,
        pages=pages or 0,
        model_calls=calls,
        cache_hits=hits,
        input_tokens=tokens_in,
        output_tokens=tokens_out,
        cost_micro_usd=micro,
        chat_calls=chat_calls,
        chat_cost_micro_usd=chat_micro,
    )


def chat_spent_since(session: Session, matter_id: int, since: datetime) -> int:
    """Micro-dollars the matter's chat calls cost from `since`, a timezone-aware time."""
    spent = session.scalar(
        select(func.coalesce(func.sum(LlmCall.cost_micro_usd), 0)).where(
            LlmCall.matter_id == matter_id,
            LlmCall.purpose == CHAT_PURPOSE,
            LlmCall.created_at >= since,
        )
    )
    return int(spent or 0)
