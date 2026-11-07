from pydantic import BaseModel, Field
from typing import Optional

from app.item_types import ItemType


class ItemOwner(BaseModel):
    """Minimal public author data embedded in item responses."""

    id: int
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True


class ItemBase(BaseModel):
    title: str
    # Responses keep a plain string so legacy rows with an unexpected type can
    # still be read. Create/Update below validate against the allowed values.
    type: str
    creator: Optional[str] = None
    year: Optional[int] = None
    rating: Optional[float] = None
    thoughts: Optional[str] = None
    cover_url: Optional[str] = None
    pages: Optional[int] = None
    current_page: Optional[int] = 0
    reading_progress: Optional[int] = 0
    is_public: bool = True


class ItemCreate(ItemBase):
    # The client must state the content type explicitly. "post" is a social
    # publication; the rest are cultural works.
    type: ItemType
    # Stars go from 1 to 5 and accept fractions (1/3, 1/2, 1/6 of a star).
    rating: Optional[float] = Field(default=None, ge=1, le=5)


class ItemUpdate(BaseModel):
    title: Optional[str] = None
    type: Optional[ItemType] = None
    creator: Optional[str] = None
    year: Optional[int] = None
    rating: Optional[float] = Field(default=None, ge=1, le=5)
    thoughts: Optional[str] = None
    cover_url: Optional[str] = None
    pages: Optional[int] = None
    current_page: Optional[int] = None
    reading_progress: Optional[int] = None
    is_public: Optional[bool] = None


class ItemResponse(ItemBase):
    id: int
    user_id: Optional[int] = None
    kind: str
    owner: Optional[ItemOwner] = None
    likes_count: int = 0
    comments_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class PublicItemResponse(BaseModel):
    """Item exposed through public profiles. No private progress data."""

    id: int
    user_id: Optional[int] = None
    title: str
    type: str
    kind: str
    creator: Optional[str] = None
    year: Optional[int] = None
    rating: Optional[float] = None
    thoughts: Optional[str] = None
    cover_url: Optional[str] = None
    likes_count: int = 0
    comments_count: int = 0

    class Config:
        from_attributes = True


class ItemVisibilityUpdate(BaseModel):
    is_public: bool


class ProgressUpdate(BaseModel):
    current_page: int
