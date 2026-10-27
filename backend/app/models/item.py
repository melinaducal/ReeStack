from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    title = Column(String, index=True, nullable=False)
    type = Column(String, nullable=False)  # book, movie, series, music, paper
    creator = Column(String)
    year = Column(Integer)
    rating = Column(Integer)
    thoughts = Column(Text)
    cover_url = Column(String)
    pages = Column(Integer)
    current_page = Column(Integer, default=0)
    reading_progress = Column(Integer, default=0)

    owner = relationship("User")
