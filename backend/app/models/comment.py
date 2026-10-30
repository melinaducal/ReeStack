from sqlalchemy import Column, Float, Integer, String, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # Fractional stars are allowed (1/3, 1/2, 1/6 of a star), so this must be REAL.
    rating = Column(Float)
    content = Column(Text, nullable=False)
    has_spoiler = Column(Boolean, default=False)

    item = relationship("Item")
    user = relationship("User")
