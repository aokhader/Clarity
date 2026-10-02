"""When each firm user last opened a matter, and what changed since."""

from datetime import datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Fact, Source, User, View
from app.schemas import ChangesOut, OpenedOut
from app.services.fact_views import fact_out, renderable_facts
from app.services.users import seeded_offset_days


def last_opened_at(
    session: Session, user: User, matter_id: int, now: datetime
) -> datetime | None:
    """The user's last visit. A stub user's first look at a matter gets its seeded date."""
    view = session.get(View, (user.id, matter_id))
    if view is not None:
        return view.last_opened_at
    offset = seeded_offset_days(user)
    if offset is None:
        return None
    seeded = View(
        user_id=user.id,
        matter_id=matter_id,
        last_opened_at=now - timedelta(days=offset),
    )
    session.add(seeded)
    session.commit()
    return seeded.last_opened_at


def matter_changes(
    session: Session, matter_id: int, user: User, now: datetime
) -> ChangesOut:
    """Facts whose Clio record was created or updated after the user's last visit."""
    since = last_opened_at(session, user, matter_id, now)
    if since is None:
        return ChangesOut(last_opened_at=None, facts=[])
    facts = session.scalars(
        renderable_facts(matter_id)
        .where(or_(Source.clio_created_at > since, Source.clio_updated_at > since))
        .order_by(
            Fact.significance.desc(), Fact.event_date.desc().nulls_last(), Fact.id
        )
    )
    return ChangesOut(last_opened_at=since, facts=[fact_out(f) for f in facts])


def record_visit(
    session: Session, matter_id: int, user: User, now: datetime
) -> OpenedOut:
    view = session.get(View, (user.id, matter_id))
    if view is None:
        session.add(View(user_id=user.id, matter_id=matter_id, last_opened_at=now))
    else:
        view.last_opened_at = now
    session.commit()
    return OpenedOut(last_opened_at=now)
