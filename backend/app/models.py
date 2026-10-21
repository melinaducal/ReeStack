"""SQLModel database tables for Reesatck."""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True, max_length=30)
    display_name: str = Field(max_length=60)
    password_hash: str = Field(max_length=256)
    bio: str = Field(default="", max_length=500)
    avatar_color: str = Field(default="#5b7f68", max_length=16)
    created_at: datetime = Field(default_factory=utcnow)


class AuthToken(SQLModel, table=True):
    __tablename__ = "auth_tokens"

    token_hash: str = Field(primary_key=True, max_length=64)
    user_id: int = Field(index=True, foreign_key="users.id")
    kind: str = Field(default="session", max_length=16, index=True)
    expires_at: int


class ContentKind:
    BOOK = "book"
    MOVIE = "movie"
    SERIES = "series"
    MUSIC = "music"
    PAPER = "paper"
    ALL = (BOOK, MOVIE, SERIES, MUSIC, PAPER)


class Content(SQLModel, table=True):
    __tablename__ = "contents"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True, max_length=200)
    creator: str = Field(default="", max_length=200)
    kind: str = Field(max_length=16, index=True)
    year: Optional[int] = None
    description: str = Field(default="", max_length=2000)
    cover_key: str = Field(default="default", max_length=80)
    total_units: Optional[int] = None
    unit_label: Optional[str] = Field(default=None, max_length=24)
    tags: str = Field(default="[]", max_length=1000)
    created_at: datetime = Field(default_factory=utcnow)


class EntryStatus:
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ALL = (PLANNED, IN_PROGRESS, COMPLETED)


class Entry(SQLModel, table=True):
    __tablename__ = "entries"
    __table_args__ = (UniqueConstraint("user_id", "content_id", name="uq_entry_owner_content"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="users.id")
    content_id: int = Field(index=True, foreign_key="contents.id")
    status: str = Field(default=EntryStatus.PLANNED, max_length=16)
    progress: int = Field(default=0, ge=0)
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    review: str = Field(default="", max_length=5000)
    updated_at: datetime = Field(default_factory=utcnow)


class Post(SQLModel, table=True):
    __tablename__ = "posts"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="users.id")
    body: str = Field(max_length=5000)
    content_id: Optional[int] = Field(default=None, foreign_key="contents.id", index=True)
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    created_at: datetime = Field(default_factory=utcnow)
    is_demo: bool = Field(default=False)


class Comment(SQLModel, table=True):
    __tablename__ = "comments"

    id: Optional[int] = Field(default=None, primary_key=True)
    post_id: int = Field(index=True, foreign_key="posts.id")
    user_id: int = Field(index=True, foreign_key="users.id")
    body: str = Field(max_length=2000)
    created_at: datetime = Field(default_factory=utcnow)


class Like(SQLModel, table=True):
    __tablename__ = "likes"
    __table_args__ = (UniqueConstraint("user_id", "post_id", name="uq_like_owner_post"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(index=True, foreign_key="users.id")
    post_id: int = Field(index=True, foreign_key="posts.id")
