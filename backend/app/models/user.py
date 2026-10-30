from sqlalchemy import Column, Integer, String, Date, Text
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    birth_date = Column(Date, nullable=False)
    hashed_password = Column(String, nullable=False)
    theme_accent = Column(String, nullable=True)
    display_name = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    avatar_url = Column(String, nullable=True)

