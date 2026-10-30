from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import uuid4

from app.database import get_db
from app.models import User, Item
from app.schemas import (
    CollectionResponse,
    UserResponse,
    UserUpdate,
    UserPublic,
    UserProfilePublic,
)
from app.auth.deps import get_current_user
from app.storage import AVATAR_DIR, ensure_upload_dirs

router = APIRouter(prefix="/users", tags=["users"])

MAX_AVATAR_BYTES = 2 * 1024 * 1024
ALLOWED_AVATAR_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def _sniff_image_type(data: bytes) -> Optional[str]:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _delete_local_avatar(avatar_url: Optional[str]):
    if not avatar_url or "/uploads/avatars/" not in avatar_url:
        return
    name = avatar_url.rsplit("/uploads/avatars/", 1)[-1].split("?")[0]
    if not name or "/" in name or "\\" in name or not name.startswith("user"):
        return
    candidate = AVATAR_DIR / name
    if candidate.is_file():
        candidate.unlink()


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserResponse)
def update_me(user_update: UserUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user_update.username and user_update.username != current_user.username:
        exists = db.query(User).filter(User.username == user_update.username).first()
        if exists:
            raise HTTPException(status_code=400, detail="El nombre de usuario ya está en uso")
        current_user.username = user_update.username
    if user_update.display_name is not None:
        current_user.display_name = user_update.display_name
    if user_update.bio is not None:
        current_user.bio = user_update.bio
    if user_update.avatar_url is not None:
        current_user.avatar_url = user_update.avatar_url
    if user_update.first_name is not None:
        current_user.first_name = user_update.first_name
    if user_update.last_name is not None:
        current_user.last_name = user_update.last_name
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/me/avatar", response_model=UserResponse)
async def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Upload a profile photo (JPEG, PNG, WebP or GIF, max 2 MB)."""
    declared_type = (file.content_type or "").lower().split(";")[0].strip()
    if declared_type not in ALLOWED_AVATAR_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato no soportado. Usá JPG, PNG, WebP o GIF",
        )

    data = await file.read(MAX_AVATAR_BYTES + 1)
    if len(data) > MAX_AVATAR_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="La imagen no puede superar los 2 MB",
        )
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo está vacío"
        )

    sniffed_type = _sniff_image_type(data)
    if sniffed_type is None or sniffed_type not in ALLOWED_AVATAR_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo no es una imagen válida",
        )

    ensure_upload_dirs()
    filename = f"user{current_user.id}_{uuid4().hex}{ALLOWED_AVATAR_TYPES[sniffed_type]}"
    (AVATAR_DIR / filename).write_bytes(data)

    previous_url = current_user.avatar_url
    current_user.avatar_url = (
        f"{str(request.base_url).rstrip('/')}/uploads/avatars/{filename}"
    )
    db.commit()
    db.refresh(current_user)
    _delete_local_avatar(previous_url)
    return current_user


@router.delete("/me/avatar", response_model=UserResponse)
def delete_avatar(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    previous_url = current_user.avatar_url
    current_user.avatar_url = None
    db.commit()
    db.refresh(current_user)
    _delete_local_avatar(previous_url)
    return current_user


@router.get("/search", response_model=List[UserPublic])
def search_users(q: str = Query(..., min_length=1), page: int = Query(1, ge=1), limit: int = Query(10, ge=1, le=50), db: Session = Depends(get_db)):
    query = db.query(User).filter((User.username.ilike(f"%{q}%")) | (User.display_name.ilike(f"%{q}%")) | (User.first_name.ilike(f"%{q}%")) | (User.last_name.ilike(f"%{q}%")))
    users = query.offset((page - 1) * limit).limit(limit).all()
    return users


@router.get("/{user_id}/public", response_model=UserProfilePublic)
def get_user_public_by_id(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return _public_profile(user, db)


@router.get("/{user_id}/collection", response_model=CollectionResponse)
def get_user_collection(
    user_id: int,
    type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Public collection of a user. Private items are never returned."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    query = db.query(Item).filter(Item.user_id == user.id, Item.is_public.is_(True))
    if type and type != "all":
        query = query.filter(Item.type == type)

    total = query.count()
    items = (
        query.order_by(Item.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return {
        "user_id": user.id,
        "username": user.username,
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
        "items": items,
    }


@router.get("/by-username/{username}/public", response_model=UserProfilePublic)
def get_user_public_by_username(username: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return _public_profile(user, db)


def _public_profile(user: User, db: Session):
    items = (
        db.query(Item)
        .filter(Item.user_id == user.id, Item.is_public.is_(True))
        .all()
    )
    stats = {
        "items_count": len(items),
        "books": len([i for i in items if i.type == "book"]),
        "movies": len([i for i in items if i.type == "movie"]),
        "series": len([i for i in items if i.type == "series"]),
        "music": len([i for i in items if i.type == "music"]),
        "papers": len([i for i in items if i.type == "paper"]),
    }
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name,
        "bio": user.bio,
        "avatar_url": user.avatar_url,
        "stats": stats,
    }
