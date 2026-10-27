from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Like, Item, User
from app.auth.deps import get_current_user

router = APIRouter(prefix="/likes", tags=["likes"])


@router.post("/item/{item_id}")
def like_item(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    existing = db.query(Like).filter(Like.item_id == item_id, Like.user_id == current_user.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ya diste like a este item")

    like = Like(item_id=item_id, user_id=current_user.id)
    db.add(like)
    db.commit()
    db.refresh(like)
    count = db.query(Like).filter(Like.item_id == item_id).count()
    return {"item_id": item_id, "liked": True, "likes_count": count}


@router.delete("/item/{item_id}")
def unlike_item(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    like = db.query(Like).filter(Like.item_id == item_id, Like.user_id == current_user.id).first()
    if not like:
        raise HTTPException(status_code=400, detail="No diste like a este item")
    db.delete(like)
    db.commit()
    count = db.query(Like).filter(Like.item_id == item_id).count()
    return {"item_id": item_id, "liked": False, "likes_count": count}


@router.get("/item/{item_id}")
def get_likes(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    count = db.query(Like).filter(Like.item_id == item_id).count()
    liked = db.query(Like).filter(Like.item_id == item_id, Like.user_id == current_user.id).first() is not None
    return {"item_id": item_id, "liked": liked, "likes_count": count}
