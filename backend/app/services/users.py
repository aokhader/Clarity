"""Stub firm users. There is no real authentication: the header switcher picks one.

Each seeded user has a default "last opened" offset so the "since you last opened"
block has something to show on a fresh database. Disclosed as a stub.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.schemas import UserOut


@dataclass(frozen=True)
class SeedUser:
    name: str
    role: str
    # Days before the first visit that this user is taken to have last opened a matter;
    # None means the user has never opened it.
    last_opened_days_ago: int | None


SEED_USERS = (
    SeedUser("Demo Attorney", "attorney", 21),
    SeedUser("Demo Paralegal", "paralegal", 7),
    SeedUser("Demo Case Manager", "case manager", None),
)


def seed_firm_users(session: Session) -> None:
    """Add any missing stub users. Safe to run on every start."""
    existing = set(session.scalars(select(User.name)))
    session.add_all(
        User(name=seed.name, role=seed.role)
        for seed in SEED_USERS
        if seed.name not in existing
    )


def list_users(session: Session) -> list[UserOut]:
    users = session.scalars(select(User).order_by(User.id))
    return [UserOut(id=u.id, name=u.name, role=u.role) for u in users]


def find_user(session: Session, user_id: int) -> User | None:
    return session.get(User, user_id)


def seeded_offset_days(user: User) -> int | None:
    seed = next((s for s in SEED_USERS if s.name == user.name), None)
    return seed.last_opened_days_ago if seed else None
