import httpx
import os
import time
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from app.database import get_db
from app.models import Item, User
from app.auth.deps import get_current_user

router = APIRouter(prefix="/books", tags=["books"])

_cache = {}
_cache_ttl = 300
_last_request_time = 0
_min_interval = 0.2


def _check_cache(key):
    if key in _cache:
        data, ts = _cache[key]
        if time.time() - ts < _cache_ttl:
            return data
    return None


def _set_cache(key, data):
    _cache[key] = (data, time.time())


def normalize_google_books(item: dict) -> dict:
    volume_info = item.get("volumeInfo", {}) or {}
    image_links = volume_info.get("imageLinks", {}) or {}
    industry_identifiers = volume_info.get("industryIdentifiers", []) or []
    categories = volume_info.get("categories", []) or []
    isbn = None
    for ident in industry_identifiers:
        if ident.get("type") in ["ISBN_13", "ISBN_10"]:
            isbn = ident.get("identifier")
            break
    cover_url = image_links.get("thumbnail") or image_links.get("smallThumbnail")
    if cover_url and cover_url.startswith("http://"):
        cover_url = cover_url.replace("http://", "https://")
    return {
        "title": volume_info.get("title"),
        "authors": volume_info.get("authors", []) or [],
        "cover_url": cover_url,
        "description": volume_info.get("description"),
        "isbn": isbn,
        "published_date": volume_info.get("publishedDate"),
        "genres": categories
    }


def normalize_open_library_docs(docs: list) -> list:
    results = []
    for doc in docs:
        if not doc.get("title"):
            continue
        isbn = None
        if doc.get("isbn"):
            isbn = doc["isbn"][0] if isinstance(doc["isbn"], list) else doc["isbn"]
        cover_id = doc.get("cover_i")
        cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg" if cover_id else None
        subjects = doc.get("subject", []) or []
        results.append({
            "title": doc.get("title"),
            "authors": doc.get("author_name", []) or [],
            "cover_url": cover_url,
            "description": None,
            "isbn": isbn,
            "published_date": doc.get("first_publish_year"),
            "genres": subjects[:5]
        })
    return results


normalize_open_library = normalize_open_library_docs


@router.get("/search")
async def search_books(
    q: str = "",
    genres: Optional[List[str]] = Query(default=None),
    genre: Optional[str] = None,
    mode: str = "or",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    genre_list = []
    if genres:
        for g in genres:
            if g is None:
                continue
            gs = str(g)
            if not gs.strip():
                continue
            for gg in gs.split(","):
                gg2 = gg.strip()
                if gg2:
                    genre_list.append(gg2)
    if genre and str(genre).strip():
        for g in str(genre).split(","):
            g2 = g.strip()
            if g2:
                genre_list.append(g2)
    seen = set()
    genre_list_clean = []
    for g in genre_list:
        gl = g.lower()
        if gl not in seen:
            seen.add(gl)
            genre_list_clean.append(g)
    
    if genre_list_clean:
        mode = mode.lower() if mode else "or"
        cache_key = f"genre:{mode}:{':'.join(sorted([x.lower() for x in genre_list_clean]))}"
        cached = _check_cache(cache_key)
        if cached is not None:
            return cached
        
        global _last_request_time
        if time.time() - _last_request_time < _min_interval:
            time.sleep(max(0, _min_interval - (time.time() - _last_request_time)))
        _last_request_time = time.time()
        
        async with httpx.AsyncClient(timeout=30.0, headers={"User-Agent": "ReeStack/1.0"}) as client:
            errors = []
            # Try Google Books first
            try:
                if mode == "and":
                    query = "subject:" + "+".join(genre_list_clean)
                    try:
                        resp = await client.get(
                            "https://www.googleapis.com/books/v1/volumes",
                            params={"q": query, "maxResults": 40, "langRestrict": "es"}
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            items = data.get("items", []) or []
                            results_google = []
                            for item in items:
                                norm = normalize_google_books(item)
                                if not norm.get("title"):
                                    continue
                                gnorm = [str(x).lower() for x in norm.get("genres", [])]
                                ok = True
                                for g in genre_list_clean:
                                    gl = g.lower()
                                    if not any(gl in x for x in gnorm):
                                        ok = False
                                        break
                                if ok and not any(r.get("title") == norm.get("title") for r in results_google):
                                    results_google.append(norm)
                            if results_google:
                                result = {"source": "google_books", "mode": "and", "genres": genre_list_clean, "results": results_google}
                                _set_cache(cache_key, result)
                                return result
                        elif resp.status_code == 429:
                            errors.append("google_books_quota_exceeded")
                        else:
                            errors.append(f"google_books_error_{resp.status_code}")
                    except Exception:
                        errors.append("google_books_request_failed")
                else:
                    results_google = []
                    for g in genre_list_clean:
                        try:
                            query = f"subject:{g}"
                            resp = await client.get(
                                "https://www.googleapis.com/books/v1/volumes",
                                params={"q": query, "maxResults": 20, "langRestrict": "es"}
                            )
                            if resp.status_code == 200:
                                data = resp.json()
                                items = data.get("items", []) or []
                                for item in items:
                                    norm = normalize_google_books(item)
                                    if norm.get("title") and not any(r.get("title") == norm.get("title") for r in results_google):
                                        results_google.append(norm)
                            elif resp.status_code == 429:
                                errors.append("google_books_quota_exceeded")
                            else:
                                errors.append(f"google_books_error_{resp.status_code}")
                        except Exception:
                            errors.append("google_books_request_failed")
                            continue
                    if results_google:
                        result = {"source": "google_books", "mode": "or", "genres": genre_list_clean, "results": results_google}
                        _set_cache(cache_key, result)
                        return result
            except Exception:
                errors.append("google_books_exception")
            
            # Fallback to Open Library
            try:
                results_ol = []
                if mode == "and":
                    key_sets = []
                    work_by_key = {}
                    for g in genre_list_clean:
                        try:
                            resp = await client.get(f"https://openlibrary.org/subjects/{g.lower().replace(' ', '_')}.json", params={"limit": 100})
                            if resp.status_code == 200:
                                data = resp.json()
                                works = data.get("works", []) or []
                                keys = set()
                                for w in works:
                                    wkey = w.get("key")
                                    if not wkey:
                                        continue
                                    keys.add(wkey)
                                    if wkey not in work_by_key:
                                        work_by_key[wkey] = w
                                if keys:
                                    key_sets.append(keys)
                            else:
                                errors.append(f"ol_{g}_status_{resp.status_code}")
                        except Exception:
                            errors.append(f"ol_{g}_failed")
                            continue
                    if key_sets:
                        common_keys = key_sets[0]
                        for s in key_sets[1:]:
                            common_keys = common_keys & s
                        if common_keys:
                            for wkey in common_keys:
                                work = work_by_key.get(wkey)
                                if not work:
                                    continue
                                title = work.get("title")
                                if not title or any(r.get("title") == title for r in results_ol):
                                    continue
                                cover_id = work.get("cover_id")
                                cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg" if cover_id else None
                                authors = work.get("authors", []) or []
                                author_names = [a.get("name", "") for a in authors if a.get("name")]
                                results_ol.append({
                                    "title": title,
                                    "authors": author_names,
                                    "cover_url": cover_url,
                                    "description": None,
                                    "isbn": None,
                                    "published_date": work.get("first_publish_year"),
                                    "genres": genre_list_clean
                                })
                    result = {"source": "open_library", "mode": "and", "genres": genre_list_clean, "results": results_ol, "fallback": True, "errors": errors}
                    _set_cache(cache_key, result)
                    return result
                else:
                    for g in genre_list_clean:
                        try:
                            resp = await client.get(f"https://openlibrary.org/subjects/{g.lower().replace(' ', '_')}.json", params={"limit": 50})
                            if resp.status_code == 200:
                                data = resp.json()
                                works = data.get("works", []) or []
                                for work in works:
                                    title = work.get("title")
                                    if not title or any(r.get("title") == title for r in results_ol):
                                        continue
                                    cover_id = work.get("cover_id")
                                    cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg" if cover_id else None
                                    authors = work.get("authors", []) or []
                                    author_names = [a.get("name", "") for a in authors if a.get("name")]
                                    results_ol.append({
                                        "title": title,
                                        "authors": author_names,
                                        "cover_url": cover_url,
                                        "description": None,
                                        "isbn": None,
                                        "published_date": work.get("first_publish_year"),
                                        "genres": [g]
                                    })
                            else:
                                errors.append(f"ol_{g}_status_{resp.status_code}")
                        except Exception:
                            errors.append(f"ol_{g}_failed")
                            continue
                    if results_ol:
                        result = {"source": "open_library", "mode": "or", "genres": genre_list_clean, "results": results_ol, "fallback": True, "errors": errors}
                        _set_cache(cache_key, result)
                        return result
                    raise HTTPException(status_code=503, detail={"error": "No se encontraron resultados en Open Library (OR)", "errors": errors})
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(status_code=503, detail={"error": "Error en fallback Open Library", "errors": errors})
    
    if not q or q.strip() == "":
        raise HTTPException(status_code=400, detail="Parámetro q requerido o géneros requeridos")
    
    query = q.strip()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://www.googleapis.com/books/v1/volumes", params={"q": query, "maxResults": 20})
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", []) or []
                results = []
                for item in items:
                    norm = normalize_google_books(item)
                    if norm.get("title"):
                        results.append(norm)
                return {"source": "google_books", "results": results}
    except Exception:
        pass
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://openlibrary.org/search.json", params={"q": query, "limit": 20})
            if resp.status_code == 200:
                data = resp.json()
                docs = data.get("docs", []) or []
                results = normalize_open_library(docs)
                results = [r for r in results if r.get("title")]
                return {"source": "open_library", "results": results}
    except Exception:
        pass
    
    raise HTTPException(status_code=503, detail="No se pudo obtener resultados de búsqueda")


@router.post("/save")
def save_book(book: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    title = book.get("title")
    if not title:
        raise HTTPException(status_code=400, detail="title requerido")
    existing = db.query(Item).filter(Item.title == title, Item.user_id == current_user.id).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe en tu biblioteca")
    authors = book.get("authors") or []
    creator = ", ".join(authors) if isinstance(authors, list) else authors
    db_item = Item(
        title=title,
        type="book",
        creator=creator,
        cover_url=book.get("cover_url"),
        thoughts=book.get("description"),
        user_id=current_user.id
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return {"message": "Guardado en biblioteca", "item": {"id": db_item.id, "title": db_item.title}}
