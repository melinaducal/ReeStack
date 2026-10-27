from pydantic import BaseModel


class LikeResponse(BaseModel):
    item_id: int
    liked: bool
    likes_count: int
