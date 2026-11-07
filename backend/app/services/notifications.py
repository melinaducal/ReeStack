"""Helpers to create user notifications from social events.

A single notification row is written per event. Like notifications are
deduplicated while unread so toggling a like does not flood the recipient.
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.models import Notification
from app.models.notification import NOTIFICATION_LIKE


def create_notification(
    db: Session,
    *,
    recipient_id: Optional[int],
    actor_id: int,
    type: str,
    item_id: Optional[int] = None,
    comment_id: Optional[int] = None,
) -> Optional[Notification]:
    """Queue a notification; the caller owns the transaction and commits it."""
    if not recipient_id or recipient_id == actor_id:
        return None

    if type == NOTIFICATION_LIKE:
        existing = (
            db.query(Notification)
            .filter(
                Notification.user_id == recipient_id,
                Notification.actor_id == actor_id,
                Notification.type == type,
                Notification.item_id == item_id,
                Notification.is_read.is_(False),
            )
            .first()
        )
        if existing:
            return existing

    notification = Notification(
        user_id=recipient_id,
        actor_id=actor_id,
        type=type,
        item_id=item_id,
        comment_id=comment_id,
    )
    db.add(notification)
    return notification
