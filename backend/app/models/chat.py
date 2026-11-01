"""Conversation storage for the recommendation assistant.

Requirement: each user keeps their own history. Tables are additive, so the
existing schema and data are never touched.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


def _utcnow() -> datetime:
    # SQLite stores naive datetimes; keep the value in UTC for consistency.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ChatConversation(Base):
    __tablename__ = "chat_conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    user = relationship("User")
    turns = relationship(
        "ChatTurn",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ChatTurn.id",
    )


class ChatTurn(Base):
    __tablename__ = "chat_turns"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(
        Integer, ForeignKey("chat_conversations.id"), nullable=False, index=True
    )
    role = Column(String, nullable=False)  # "user" | "assistant"
    content = Column(Text, nullable=False)
    # JSON snapshot of the recommendations returned in this turn.
    recommendations = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    conversation = relationship("ChatConversation", back_populates="turns")
