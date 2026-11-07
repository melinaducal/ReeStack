from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, text
from sqlalchemy.orm import relationship

from app.database import Base

NOTIFICATION_FRIEND_REQUEST = "friend_request"
NOTIFICATION_FRIEND_ACCEPTED = "friend_accepted"
NOTIFICATION_LIKE = "like"
NOTIFICATION_COMMENT = "comment"


class Notification(Base):
    """An event addressed to a single user.

    ``user_id`` is the recipient; ``actor_id`` is the user who triggered the
    event. A notification about social content keeps the item reference so the
    recipient can open the post directly.
    """

    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(String, nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=True)
    comment_id = Column(Integer, ForeignKey("comments.id"), nullable=True)
    is_read = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
        index=True,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = relationship("User", foreign_keys=[user_id])
    actor = relationship("User", foreign_keys=[actor_id])
    item = relationship("Item")
    comment = relationship("Comment")
