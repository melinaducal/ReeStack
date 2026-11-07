from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import Notification, User
from app.schemas import NotificationResponse, UnreadCountResponse

router = APIRouter(prefix="/notifications", tags=["notifications"])

COMMENT_PREVIEW_LENGTH = 160


def _serialize(notification: Notification) -> dict:
    preview = None
    if notification.comment and notification.comment.content:
        preview = notification.comment.content.strip()
        if len(preview) > COMMENT_PREVIEW_LENGTH:
            preview = f"{preview[:COMMENT_PREVIEW_LENGTH]}…"
    return {
        "id": notification.id,
        "type": notification.type,
        "is_read": notification.is_read,
        "created_at": notification.created_at,
        "actor": notification.actor,
        "item": notification.item,
        "comment_preview": preview,
    }


def _base_query(db: Session, user_id: int):
    return db.query(Notification).options(
        joinedload(Notification.actor),
        joinedload(Notification.item),
        joinedload(Notification.comment),
    ).filter(Notification.user_id == user_id)


@router.get("/unread-count", response_model=UnreadCountResponse)
def unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = (
        db.query(Notification)
        .filter(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
        .count()
    )
    return {"count": count}


@router.get("", response_model=List[NotificationResponse])
@router.get("/", response_model=List[NotificationResponse], include_in_schema=False)
def list_notifications(
    unread_only: bool = Query(False),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = _base_query(db, current_user.id)
    if unread_only:
        query = query.filter(Notification.is_read.is_(False))

    notifications = (
        query.order_by(
            Notification.is_read.asc(),
            Notification.created_at.desc(),
            Notification.id.desc(),
        )
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return [_serialize(notification) for notification in notifications]


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_as_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notification = (
        db.query(Notification)
        .options(
            joinedload(Notification.actor),
            joinedload(Notification.item),
            joinedload(Notification.comment),
        )
        .filter(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
        .first()
    )
    if not notification:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")

    if not notification.is_read:
        notification.is_read = True
        db.commit()
        db.refresh(notification)
    return _serialize(notification)


@router.post("/read-all")
def mark_all_as_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    updated = (
        db.query(Notification)
        .filter(
            Notification.user_id == current_user.id,
            Notification.is_read.is_(False),
        )
        .update({Notification.is_read: True}, synchronize_session=False)
    )
    db.commit()
    return {"updated": updated}
