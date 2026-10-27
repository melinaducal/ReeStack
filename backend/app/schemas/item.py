from pydantic import BaseModel
from typing import Optional


class ItemBase(BaseModel):
    title: str
    type: str
    creator: Optional[str] = None
    year: Optional[int] = None
    rating: Optional[int] = None
    thoughts: Optional[str] = None
    cover_url: Optional[str] = None
    pages: Optional[int] = None
    current_page: Optional[int] = 0
    reading_progress: Optional[int] = 0


class ItemCreate(ItemBase):
    pass


class ItemUpdate(BaseModel):
    title: Optional[str] = None
    type: Optional[str] = None
    creator: Optional[str] = None
    year: Optional[int] = None
    rating: Optional[int] = None
    thoughts: Optional[str] = None
    cover_url: Optional[str] = None
    pages: Optional[int] = None
    current_page: Optional[int] = None
    reading_progress: Optional[int] = None


class ItemResponse(ItemBase):
    id: int
    user_id: Optional[int] = None

    class Config:
        from_attributes = True


class ProgressUpdate(BaseModel):
    current_page: int
