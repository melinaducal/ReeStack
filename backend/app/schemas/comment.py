from pydantic import BaseModel, Field
from typing import Optional

class CommentBase(BaseModel):
    rating: Optional[float] = None
    content: str
    has_spoiler: bool = False

class CommentCreate(CommentBase):
    # Stars go from 1 to 5 and accept fractions (1/3, 1/2, 1/6 of a star).
    rating: Optional[float] = Field(default=None, ge=1, le=5)

class CommentResponse(CommentBase):
    id: int
    item_id: int
    user_id: int
    username: Optional[str] = None

    class Config:
        from_attributes = True
