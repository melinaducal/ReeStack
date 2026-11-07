from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models import Comment, Item, User
from app.models.notification import NOTIFICATION_COMMENT
from app.schemas import CommentCreate, CommentResponse, CommentUpdate
from app.auth.deps import get_current_user, get_optional_user
from app.services.notifications import create_notification

router = APIRouter(prefix="/comments", tags=["comments"])


def _visible_item(db: Session, item_id: int, viewer: Optional[User]) -> Item:
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    if not item.is_public and (viewer is None or viewer.id != item.user_id):
        # 404 instead of 403 so private items do not reveal their existence.
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    return item


def _serialize(comment: Comment, author: Optional[User], viewer: Optional[User]) -> dict:
    return {
        "id": comment.id,
        "item_id": comment.item_id,
        "user_id": comment.user_id,
        "username": author.username if author else None,
        "display_name": author.display_name if author else None,
        "avatar_url": author.avatar_url if author else None,
        "rating": comment.rating,
        "content": comment.content,
        "has_spoiler": comment.has_spoiler,
        "created_at": comment.created_at,
        "is_owner": viewer is not None and viewer.id == comment.user_id,
    }


def _authors_by_id(db: Session, comments: List[Comment]) -> dict:
    user_ids = {comment.user_id for comment in comments}
    if not user_ids:
        return {}
    authors = db.query(User).filter(User.id.in_(user_ids)).all()
    return {author.id: author for author in authors}


@router.get("/item/{item_id}", response_model=List[CommentResponse])
def get_comments(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    _visible_item(db, item_id, current_user)
    comments = (
        db.query(Comment)
        .filter(Comment.item_id == item_id)
        .order_by(Comment.created_at.asc(), Comment.id.asc())
        .all()
    )
    authors = _authors_by_id(db, comments)
    return [
        _serialize(comment, authors.get(comment.user_id), current_user)
        for comment in comments
    ]


@router.post("/item/{item_id}", response_model=CommentResponse)
def create_comment(
    item_id: int,
    comment: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = _visible_item(db, item_id, current_user)

    # The author always comes from the JWT. Any user_id in the body is ignored
    # by the schema and never reaches the model.
    db_comment = Comment(
        item_id=item_id,
        user_id=current_user.id,
        **comment.model_dump(),
    )
    db.add(db_comment)
    db.flush()
    create_notification(
        db,
        recipient_id=item.user_id,
        actor_id=current_user.id,
        type=NOTIFICATION_COMMENT,
        item_id=item.id,
        comment_id=db_comment.id,
    )
    db.commit()
    db.refresh(db_comment)
    return _serialize(db_comment, current_user, current_user)


@router.get("/item/{item_id}/rating")
def get_rating_summary(item_id: int, db: Session = Depends(get_db)):
    comments = (
        db.query(Comment)
        .filter(Comment.item_id == item_id, Comment.rating != None)
        .all()
    )
    if not comments:
        return {"average": 0, "count": 0}
    total = sum(c.rating for c in comments)
    # Three decimals keep fractional stars (1/3, 1/6) meaningful.
    avg = round(total / len(comments), 3)
    return {"average": avg, "count": len(comments)}


@router.put("/{comment_id}", response_model=CommentResponse)
def update_comment(
    comment_id: int,
    comment_update: CommentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comentario no encontrado")
    if comment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado para editar este comentario",
        )

    update_data = comment_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(comment, key, value)

    db.commit()
    db.refresh(comment)
    return _serialize(comment, current_user, current_user)


@router.delete("/{comment_id}")
def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comentario no encontrado")
    if comment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No autorizado para eliminar este comentario",
        )

    db.delete(comment)
    db.commit()
    return {"message": "Comentario eliminado", "id": comment_id}
