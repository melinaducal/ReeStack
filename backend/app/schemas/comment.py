from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


def _clean_content(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("El comentario no puede estar vacío")
    return cleaned


class CommentBase(BaseModel):
    rating: Optional[float] = None
    content: str
    has_spoiler: bool = False


class CommentCreate(CommentBase):
    # Stars go from 1 to 5 and accept fractions (1/3, 1/2, 1/6 of a star).
    rating: Optional[float] = Field(default=None, ge=1, le=5)

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, value: str) -> str:
        return _clean_content(value)


class CommentUpdate(BaseModel):
    content: Optional[str] = None
    rating: Optional[float] = Field(default=None, ge=1, le=5)
    has_spoiler: Optional[bool] = None

    @field_validator("content")
    @classmethod
    def content_not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        return _clean_content(value)


class CommentResponse(BaseModel):
    id: int
    item_id: int
    user_id: int
    username: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None
    rating: Optional[float] = None
    content: str
    has_spoiler: bool = False
    created_at: Optional[datetime] = None
    # True only for the authenticated author, so the UI can show edit/delete.
    is_owner: bool = False

    class Config:
        from_attributes = True
