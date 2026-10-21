"""Pydantic request/response schemas for the Reesatck API."""
import re
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

KindLiteral = Literal["book", "movie", "series", "music", "paper"]
StatusLiteral = Literal["planned", "in_progress", "completed"]

USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{2,29}$")


class UserRegister(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    display_name: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=10, max_length=200)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, v: str) -> str:
        v = v.strip().lower()
        if not USERNAME_RE.match(v):
            raise ValueError("Username must be 3-30 characters: lowercase letters, digits, dot, dash, underscore")
        return v


class UserLogin(BaseModel):
    username: str = Field(min_length=1, max_length=30)
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    bio: str
    avatar_color: str


class ContentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    creator: str = Field(default="", max_length=200)
    kind: KindLiteral
    year: Optional[int] = Field(default=None, ge=0, le=3000)
    description: str = Field(default="", max_length=2000)
    cover_key: str = Field(default="default", max_length=80)
    total_units: Optional[int] = Field(default=None, ge=1, le=100000)
    unit_label: Optional[str] = Field(default=None, max_length=24)
    tags: List[str] = Field(default_factory=list, max_length=20)

    @field_validator("title")
    @classmethod
    def strip_title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Title cannot be empty")
        return v

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, v: List[str]) -> List[str]:
        return [t.strip()[:40] for t in v if t.strip()][:20]


class CollectionAdd(BaseModel):
    content_id: int
    status: StatusLiteral = "planned"


class EntryPatch(BaseModel):
    status: Optional[StatusLiteral] = None
    progress: Optional[int] = Field(default=None, ge=0, le=100000)
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    review: Optional[str] = Field(default=None, max_length=5000)


class PostCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    content_id: Optional[int] = None
    rating: Optional[int] = Field(default=None, ge=1, le=5)

    @field_validator("body")
    @classmethod
    def strip_body(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Post body cannot be empty")
        return v


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)

    @field_validator("body")
    @classmethod
    def strip_body(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Comment cannot be empty")
        return v


class LikeOut(BaseModel):
    liked: bool
    like_count: int


class AssistantChat(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class AssistantStatus(BaseModel):
    configured: bool
    model: Optional[str] = None


class HealthOut(BaseModel):
    status: str
