"""The stored brief, with every citation checked before it reaches the screen."""

import logging

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Digest, DigestKind, Fact
from app.schemas import BriefContent, BriefOut, BriefSentenceOut
from app.services.fact_views import fact_ref, renderable_facts

log = logging.getLogger(__name__)


class BriefNotFound(LookupError):
    pass


def matter_brief(session: Session, matter_id: int) -> BriefOut:
    digest = session.scalars(
        select(Digest)
        .where(Digest.matter_id == matter_id, Digest.kind == DigestKind.BRIEF)
        .order_by(Digest.created_at.desc(), Digest.id.desc())
    ).first()
    if digest is None:
        raise BriefNotFound(f"matter {matter_id} has no brief yet")
    try:
        content = BriefContent.model_validate(digest.content_json)
    except ValidationError as error:
        log.warning("brief %s does not match BriefContent: %s", digest.id, error)
        raise BriefNotFound(
            f"the stored brief for matter {matter_id} is invalid"
        ) from error

    cited = {i for s in content.sentences for i in s.fact_ids} | set(
        content.stage_fact_ids
    )
    facts: dict[int, Fact] = {
        f.id: f
        for f in session.scalars(renderable_facts(matter_id).where(Fact.id.in_(cited)))
    }
    # A sentence is shown only if every fact it cites can be shown; otherwise part of
    # what it says would be on screen without a source.
    sentences = [
        BriefSentenceOut(text=s.text, facts=[fact_ref(facts[i]) for i in s.fact_ids])
        for s in content.sentences
        if all(i in facts for i in s.fact_ids)
    ]
    return BriefOut(
        headline=content.headline,
        stage=content.stage,
        stage_facts=[fact_ref(facts[i]) for i in content.stage_fact_ids if i in facts],
        sentences=sentences,
        open_questions=content.open_questions,
        generated_at=digest.created_at,
    )
