from pydantic import BaseModel
from typing import Optional

class CommentBase(BaseModel):
    rating: Optional[int] = None
    content: str
    has_spoiler: bool = False

class CommentCreate(CommentBase):
    pass

class CommentResponse(CommentBase):
    id: int
    item_id: int
    user_id: int
    username: Optional[str] = None

    class Config:
        from_attributes = True
