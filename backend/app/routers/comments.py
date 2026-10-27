from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import Comment, User
from app.schemas import CommentCreate, CommentResponse
from app.auth.deps import get_current_user

router = APIRouter(prefix="/comments", tags=["comments"])

@router.get("/item/{item_id}", response_model=List[CommentResponse])
def get_comments(item_id: int, db: Session = Depends(get_db)):
    comments = db.query(Comment).filter(Comment.item_id == item_id).all()
    result = []
    for comment in comments:
        user = db.query(User).filter(User.id == comment.user_id).first()
        result.append({
            "id": comment.id,
            "item_id": comment.item_id,
            "user_id": comment.user_id,
            "rating": comment.rating,
            "content": comment.content,
            "has_spoiler": comment.has_spoiler,
            "username": user.username if user else None
        })
    return result

@router.post("/item/{item_id}", response_model=CommentResponse)
def create_comment(item_id: int, comment: CommentCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db_comment = Comment(item_id=item_id, user_id=current_user.id, **comment.model_dump())
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)
    user = db.query(User).filter(User.id == db_comment.user_id).first()
    return {
        "id": db_comment.id,
        "item_id": db_comment.item_id,
        "user_id": db_comment.user_id,
        "rating": db_comment.rating,
        "content": db_comment.content,
        "has_spoiler": db_comment.has_spoiler,
        "username": user.username if user else None
    }

@router.get("/item/{item_id}/rating")
def get_rating_summary(item_id: int, db: Session = Depends(get_db)):
    comments = db.query(Comment).filter(Comment.item_id == item_id, Comment.rating != None).all()
    if not comments:
        return {"average": 0, "count": 0}
    total = sum(c.rating for c in comments)
    avg = round(total / len(comments), 1)
    return {"average": avg, "count": len(comments)}
