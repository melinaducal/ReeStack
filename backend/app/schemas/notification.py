from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class NotificationActor(BaseModel):
    id: int
    username: str
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True


class NotificationItem(BaseModel):
    id: int
    title: str
    type: str


class NotificationResponse(BaseModel):
    id: int
    type: str
    is_read: bool
    created_at: datetime
    actor: Optional[NotificationActor] = None
    item: Optional[NotificationItem] = None
    comment_preview: Optional[str] = None


class UnreadCountResponse(BaseModel):
    count: int
