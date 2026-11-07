from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from .user import UserPublic


class FriendResponse(BaseModel):
    friendship_id: int
    user: UserPublic
    since: datetime


class FriendRequestResponse(BaseModel):
    friendship_id: int
    user: UserPublic
    created_at: datetime
    direction: str


class FriendshipStatusResponse(BaseModel):
    status: str
    friendship_id: Optional[int] = None
