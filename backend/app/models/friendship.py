from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base

FRIENDSHIP_PENDING = "pending"
FRIENDSHIP_ACCEPTED = "accepted"
FRIENDSHIP_REJECTED = "rejected"


class Friendship(Base):
    """A single directed request between two users.

    Two constraints protect the pair at database level:

    * ``uq_friendship_pair`` keeps one row per (requester, addressee).
    * ``uq_friendship_canonical_pair`` indexes ``min(requester_id,
      addressee_id)`` and ``max(requester_id, addressee_id)``, so ``A -> B``
      and ``B -> A`` can never coexist even when both requests are processed
      concurrently. Direction is still stored in the row; only the database
      uniqueness key ignores it.

    The friends router resolves a reverse pending request by accepting the
    existing row instead of creating a mirrored one.
    """

    __tablename__ = "friendships"

    id = Column(Integer, primary_key=True, index=True)
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    addressee_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    status = Column(
        String,
        nullable=False,
        default=FRIENDSHIP_PENDING,
        server_default=FRIENDSHIP_PENDING,
        index=True,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    responded_at = Column(DateTime, nullable=True)

    requester = relationship("User", foreign_keys=[requester_id])
    addressee = relationship("User", foreign_keys=[addressee_id])

    __table_args__ = (
        UniqueConstraint("requester_id", "addressee_id", name="uq_friendship_pair"),
        Index(
            "uq_friendship_canonical_pair",
            func.min(requester_id, addressee_id),
            func.max(requester_id, addressee_id),
            unique=True,
        ),
        CheckConstraint("requester_id <> addressee_id", name="ck_friendship_not_self"),
    )
