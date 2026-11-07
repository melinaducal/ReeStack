from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from app.database import get_db
from app.item_types import POST_TYPE
from app.models import Comment, Item, Like, User
from app.schemas import (
    ItemCreate,
    ItemResponse,
    ItemUpdate,
    ItemVisibilityUpdate,
    ProgressUpdate,
)
from app.auth.deps import get_current_user, get_optional_user

router = APIRouter(prefix="/items", tags=["items"])


def _attach_social_counts(db: Session, items: List[Item]) -> List[Item]:
    """Attach real like/comment counters without one query per item."""
    item_ids = [item.id for item in items]
    if not item_ids:
        return items

    like_rows = (
        db.query(Like.item_id, func.count(Like.id))
        .filter(Like.item_id.in_(item_ids))
        .group_by(Like.item_id)
        .all()
    )
    comment_rows = (
        db.query(Comment.item_id, func.count(Comment.id))
        .filter(Comment.item_id.in_(item_ids))
        .group_by(Comment.item_id)
        .all()
    )
    like_counts = dict(like_rows)
    comment_counts = dict(comment_rows)

    for item in items:
        item.likes_count = like_counts.get(item.id, 0)
        item.comments_count = comment_counts.get(item.id, 0)
    return items


@router.get("/", response_model=List[ItemResponse])
def get_items(
    type: Optional[str] = None,
    mine: bool = False,
    include_posts: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Item).options(joinedload(Item.owner))
    if mine:
        query = query.filter(Item.user_id == current_user.id)
    else:
        # Public catalogue: only public items plus the caller's own items.
        query = query.filter(
            or_(Item.is_public.is_(True), Item.user_id == current_user.id)
        )
    if not include_posts:
        # Library views ask for cultural works only. Social posts are still
        # available through the feed, their detail page and type=post.
        query = query.filter(Item.type != POST_TYPE)
    if type and type != "all":
        query = query.filter(Item.type == type)
    return _attach_social_counts(db, query.all())


@router.get("/feed", response_model=List[ItemResponse])
def get_feed(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(Item).options(joinedload(Item.owner)).filter(
        Item.user_id.isnot(None),
        or_(Item.is_public.is_(True), Item.user_id == current_user.id),
    )
    return _attach_social_counts(db, query.order_by(Item.id.desc()).all())


@router.get("/{item_id}", response_model=ItemResponse)
def get_item(item_id: int, db: Session = Depends(get_db), current_user: Optional[User] = Depends(get_optional_user)):
    item = db.query(Item).options(joinedload(Item.owner)).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if not item.is_public and (current_user is None or current_user.id != item.user_id):
        # 404 instead of 403 so private items do not reveal their existence.
        raise HTTPException(status_code=404, detail="Item not found")
    _attach_social_counts(db, [item])
    return item


@router.post("/", response_model=ItemResponse)
def create_item(item: ItemCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_item = Item(**item.model_dump(), user_id=current_user.id)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


@router.put("/{item_id}", response_model=ItemResponse)
def update_item(item_id: int, item_update: ItemUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.user_id is None or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado para modificar este item")

    update_data = item_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{item_id}/visibility", response_model=ItemResponse)
def update_visibility(item_id: int, visibility: ItemVisibilityUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.user_id is None or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado para modificar este item")

    item.is_public = visibility.is_public
    db.commit()
    db.refresh(item)
    return item


@router.put("/{item_id}/progress", response_model=ItemResponse)
def update_progress(item_id: int, progress: ProgressUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.user_id is None or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado para modificar este item")
    if not item.pages or item.pages <= 0:
        raise HTTPException(status_code=400, detail="El libro no tiene total de páginas definido")
    if progress.current_page < 0 or progress.current_page > item.pages:
        raise HTTPException(status_code=400, detail="La página debe estar entre 0 y el total de páginas")

    item.current_page = progress.current_page
    item.reading_progress = int((progress.current_page / item.pages) * 100)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}")
def delete_item(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if item.user_id is None or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No autorizado para eliminar este item")
    db.delete(item)
    db.commit()
    return {"message": "Item deleted successfully"}
