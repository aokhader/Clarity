"""The draft checker applied to a provider's link, and the lock on a share's note.

"Supported" means the link already shows the figure: `shown_values` walks the payload
the link serves. The share's note is the one free text that reaches the provider, so
the server refuses a note that would disclose what the link withholds, when a share is
created and on any change to its note or settings (rule 4, D25). `provider_payload`
also drops a locked note from what it serves, for shares stored before this check.
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Share, User
from app.schemas import DraftCheckOut, DraftMentionOut, ShareCreate, ShareUpdate
from app.services import shares
from app.services.draft_check import check_text
from app.services.provider_view import provider_payload, visible_by_id
from app.services.share_values import shown_values, withheld_values
from app.services.visibility import share_is_live


class NoteLocked(ValueError):
    """The note discloses what the link withholds; `locked` holds the spans."""

    def __init__(self, locked: list[DraftMentionOut]) -> None:
        super().__init__("The note states what this link keeps from the provider")
        self.locked = locked


def check_share_draft(
    session: Session, share: Share, text: str, now: datetime
) -> DraftCheckOut:
    """Check text meant for the provider holding `share`. Raises ShareGone if it is not live."""
    payload = provider_payload(session, share, now)
    return check_text(
        text,
        shown_values(payload, visible_by_id(session, share, now)),
        withheld_values(session, share, now),
    )


def create_share(
    session: Session, matter_id: int, body: ShareCreate, user: User, now: datetime
) -> Share:
    """Create the link, unless its note is locked. Raises NoteLocked or NotAProvider."""
    share = shares.draft_share(session, matter_id, body, now)
    require_sendable_note(session, share, now)
    return shares.save_share(session, share, user)


def update_share(
    session: Session, share: Share, body: ShareUpdate, now: datetime
) -> Share:
    """Apply the change, unless it leaves the note locked; then nothing changes."""
    shares.apply_update(share, body)
    try:
        require_sendable_note(session, share, now)
    except NoteLocked:
        session.rollback()  # the share reloads as it was stored
        raise
    session.commit()
    return share


def require_sendable_note(session: Session, share: Share, now: datetime) -> None:
    if not share.note or not share_is_live(share, now):
        return  # an expired or revoked link serves nothing
    checked = check_share_draft(session, share, share.note, now)
    locked = [
        m for s in checked.sentences for m in s.mentions if m.verdict == "do_not_send"
    ]
    if locked:
        raise NoteLocked(locked)
