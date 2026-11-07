from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Like, Item, User
from app.models.notification import NOTIFICATION_LIKE
from app.auth.deps import get_current_user
from app.services.notifications import create_notification

router = APIRouter(prefix="/likes", tags=["likes"])


def _require_item(db: Session, item_id: int) -> Item:
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    return item


def _state(db: Session, item_id: int, user_id: int) -> dict:
    count = db.query(Like).filter(Like.item_id == item_id).count()
    liked = (
        db.query(Like)
        .filter(Like.item_id == item_id, Like.user_id == user_id)
        .first()
        is not None
    )
    return {"item_id": item_id, "liked": liked, "likes_count": count}


@router.post("/item/{item_id}")
def like_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = _require_item(db, item_id)
    existing = (
        db.query(Like)
        .filter(Like.item_id == item_id, Like.user_id == current_user.id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Ya diste like a este item")

    like = Like(item_id=item_id, user_id=current_user.id)
    db.add(like)
    create_notification(
        db,
        recipient_id=item.user_id,
        actor_id=current_user.id,
        type=NOTIFICATION_LIKE,
        item_id=item.id,
    )
    try:
        db.commit()
    except IntegrityError:
        # The unique constraint (item_id, user_id) is the last line of defence
        # against two concurrent requests creating two active likes.
        db.rollback()
        raise HTTPException(status_code=400, detail="Ya diste like a este item")
    db.refresh(like)
    return _state(db, item_id, current_user.id)


@router.delete("/item/{item_id}")
def unlike_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_item(db, item_id)

    like = (
        db.query(Like)
        .filter(Like.item_id == item_id, Like.user_id == current_user.id)
        .first()
    )
    if not like:
        raise HTTPException(status_code=400, detail="No diste like a este item")
    db.delete(like)
    db.commit()
    return _state(db, item_id, current_user.id)


@router.get("/item/{item_id}")
def get_likes(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_item(db, item_id)
    return _state(db, item_id, current_user.id)
