from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models import Item, User
from app.schemas import ItemCreate, ItemResponse, ItemUpdate, ProgressUpdate
from app.auth.deps import get_current_user

router = APIRouter(prefix="/items", tags=["items"])


@router.get("/", response_model=List[ItemResponse])
def get_items(type: Optional[str] = None, mine: bool = False, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(Item)
    if mine:
        query = query.filter(Item.user_id == current_user.id)
    if type and type != "all":
        query = query.filter(Item.type == type)
    return query.all()


@router.get("/feed", response_model=List[ItemResponse])
def get_feed(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(Item).filter(Item.user_id.isnot(None))
    return query.order_by(Item.id.desc()).all()


@router.get("/{item_id}", response_model=ItemResponse)
def get_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(Item).filter(Item.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
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
