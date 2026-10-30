import asyncio
import time
import unicodedata
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import Item, User

router = APIRouter(prefix="/books", tags=["books"])

GOOGLE_BOOKS_URL = "https://www.googleapis.com/books/v1/volumes"
OPEN_LIBRARY_SUBJECT_URL = "https://openlibrary.org/subjects/{slug}.json"

_cache = {}
_cache_ttl = 300


def _check_cache(key):
    if key in _cache:
        data, ts = _cache[key]
        if time.time() - ts < _cache_ttl:
            return data
    return None


def _set_cache(key, data):
    _cache[key] = (data, time.time())


def _norm_text(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower().replace("-", " ").replace("_", " ")
    return " ".join(text.split())


# Canonical genre table: Spanish label + Google Books subject + Open Library slug.
# Every entry maps a real genre to terms that actually exist in the providers,
# so we never invent genres nor assign one without provider evidence.
GENRE_TABLE = {}


def _register_genre(label, slugs, subjects, aliases=()):
    entry = {"label": label, "slugs": list(slugs), "subjects": list(subjects)}
    for alias in (label, *aliases):
        GENRE_TABLE[_norm_text(alias)] = entry


_register_genre("Ficción", ["fiction"], ["fiction"], ["novela", "novelas", "fiction"])
_register_genre("Romance", ["romance"], ["romance"], ["romántico", "romántica"])
_register_genre("Misterio", ["mystery"], ["mystery"], ["mystery", "detectivesco"])
_register_genre("Fantasía", ["fantasy"], ["fantasy"], ["fantasy"])
_register_genre(
    "Ciencia Ficción",
    ["science_fiction"],
    ["science fiction"],
    ["ciencia ficcion", "sci fi", "science fiction", "cf"],
)
_register_genre("Terror", ["horror"], ["horror"], ["horror"])
_register_genre(
    "Histórico",
    ["historical_fiction"],
    ["historical fiction"],
    ["historical fiction", "novela historica"],
)
_register_genre("Biografía", ["biography"], ["biography"], ["biography", "memorias", "memoir"])
_register_genre("Autoayuda", ["self_help"], ["self-help"], ["self help", "self-help"])
_register_genre("Poesía", ["poetry"], ["poetry"], ["poetry"])
_register_genre("Thriller", ["thriller"], ["thriller"], ["suspenso", "suspense"])
_register_genre("Aventura", ["adventure"], ["adventure"], ["adventure"])
_register_genre("Drama", ["drama"], ["drama"])
_register_genre(
    "Infantil",
    ["juvenile_fiction", "children_s_literature"],
    ["juvenile fiction", "children's literature"],
    ["children", "childrens", "children's"],
)
_register_genre(
    "Juvenil",
    ["young_adult", "juvenile_fiction"],
    ["young adult", "juvenile fiction"],
    ["young adult", "ya"],
)


def resolve_genres(raw_values) -> List[dict]:
    """Turn user input (ES/EN, with or without accents, comma separated) into canonical genres."""
    resolved = []
    seen = set()

    for raw in raw_values:
        if raw is None:
            continue
        for part in str(raw).split(","):
            part = part.strip()
            if not part:
                continue
            entry = GENRE_TABLE.get(_norm_text(part))
            if entry:
                label = entry["label"]
                slugs = entry["slugs"]
                subjects = entry["subjects"]
            else:
                label = part
                slugs = [_norm_text(part).replace(" ", "_")]
                subjects = [part]
            key = _norm_text(label)
            if key in seen:
                continue
            seen.add(key)
            resolved.append({"label": label, "slugs": slugs, "subjects": subjects})

    return resolved


def _extract_genre_values(request: Request, genres: Optional[List[str]], genre: Optional[str]):
    values = []
    # Axios serializes arrays as genres[]=a&genres[]=b, other clients use genres=a&genres=b.
    values.extend(request.query_params.getlist("genres"))
    values.extend(request.query_params.getlist("genres[]"))
    if genre:
        values.append(genre)
    if genres:
        values.extend(genres)
    return values


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
        "genres": categories,
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
        results.append(
            {
                "title": doc.get("title"),
                "authors": doc.get("author_name", []) or [],
                "cover_url": cover_url,
                "description": None,
                "isbn": isbn,
                "published_date": doc.get("first_publish_year"),
                "genres": subjects[:5],
            }
        )
    return results


normalize_open_library = normalize_open_library_docs


def _title_key(item: dict) -> str:
    return _norm_text(item.get("title"))


def _union_genres(*lists):
    merged = []
    seen = set()
    for values in lists:
        for value in values or []:
            key = _norm_text(value)
            if key and key not in seen:
                seen.add(key)
                merged.append(value)
    return merged


async def _google_subject(client, term: str, errors: list, max_results: int = 20):
    try:
        response = await client.get(
            GOOGLE_BOOKS_URL,
            params={"q": f'subject:"{term}"', "maxResults": max_results},
        )
    except httpx.HTTPError:
        errors.append(f"google_request_failed:{term}")
        return []

    if response.status_code != 200:
        errors.append(f"google_status_{response.status_code}:{term}")
        return []

    items = (response.json().get("items") or [])
    results = []
    seen = set()
    for item in items:
        norm = normalize_google_books(item)
        key = _title_key(norm)
        if norm.get("title") and key not in seen:
            seen.add(key)
            results.append(norm)
    return results


async def _open_library_subject(client, genre: dict, errors: list):
    for slug in genre["slugs"]:
        try:
            response = await client.get(
                OPEN_LIBRARY_SUBJECT_URL.format(slug=slug), params={"limit": 50}
            )
        except httpx.HTTPError:
            errors.append(f"open_library_request_failed:{slug}")
            continue

        if response.status_code != 200:
            errors.append(f"open_library_status_{response.status_code}:{slug}")
            continue

        works = response.json().get("works") or []
        results = []
        seen = set()
        for work in works:
            title = work.get("title")
            key = _title_key({"title": title})
            if not title or key in seen:
                continue
            seen.add(key)
            cover_id = work.get("cover_id")
            authors = work.get("authors", []) or []
            results.append(
                {
                    "title": title,
                    "authors": [a.get("name", "") for a in authors if a.get("name")],
                    "cover_url": (
                        f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"
                        if cover_id
                        else None
                    ),
                    "description": None,
                    "isbn": None,
                    "published_date": work.get("first_publish_year"),
                    "genres": [],
                }
            )
        if results:
            return results

    return []


async def _genre_results(client, genre: dict, errors: list):
    """Return provider-backed results for one canonical genre and the source used."""
    results = []
    source = None

    for term in genre["subjects"]:
        results = await _google_subject(client, term, errors)
        if results:
            source = "google_books"
            break

    if not results:
        results = await _open_library_subject(client, genre, errors)
        if results:
            source = "open_library"

    for item in results:
        item["genres"] = _union_genres(item.get("genres"), [genre["label"]])
        item["matched_genres"] = [genre["label"]]

    return results, source


async def _search_by_genres(genres: List[dict], mode: str):
    errors = []
    sources = set()
    all_items = []

    async with httpx.AsyncClient(
        timeout=20.0, headers={"User-Agent": "ReeStack/1.0"}
    ) as client:
        if mode == "and":
            per_genre = []
            for genre in genres:
                results, source = await _genre_results(client, genre, errors)
                if source:
                    sources.add(source)
                per_genre.append({_title_key(item): item for item in results})
                await asyncio.sleep(0.05)

            common = set(per_genre[0]) if per_genre else set()
            for title_keys in per_genre[1:]:
                common &= set(title_keys)

            for key in sorted(common):
                item = per_genre[0][key]
                item["matched_genres"] = [genre["label"] for genre in genres]
                item["genres"] = _union_genres(
                    item.get("genres"), [genre["label"] for genre in genres]
                )
                all_items.append(item)
        else:
            merged = {}
            order = []
            for genre in genres:
                results, source = await _genre_results(client, genre, errors)
                if source:
                    sources.add(source)
                for item in results:
                    key = _title_key(item)
                    if not key:
                        continue
                    if key not in merged:
                        merged[key] = item
                        order.append(key)
                    else:
                        existing = merged[key]
                        existing["genres"] = _union_genres(
                            existing.get("genres"), item.get("genres")
                        )
                        existing["matched_genres"] = _union_genres(
                            existing.get("matched_genres"), item.get("matched_genres")
                        )
                await asyncio.sleep(0.05)
            all_items = [merged[key] for key in order]

    return all_items, sources, errors


@router.get("/search")
async def search_books(
    request: Request,
    q: str = "",
    genres: Optional[List[str]] = Query(default=None),
    genre: Optional[str] = None,
    mode: str = "or",
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    resolved = resolve_genres(_extract_genre_values(request, genres, genre))

    if resolved:
        mode = (mode or "or").lower()
        if mode not in ("or", "and"):
            raise HTTPException(status_code=400, detail="mode debe ser 'or' o 'and'")

        cache_key = "genre:{}:{}:{}:{}".format(
            mode,
            ":".join(sorted(_norm_text(g["label"]) for g in resolved)),
            page,
            limit,
        )
        cached = _check_cache(cache_key)
        if cached is not None:
            return cached

        all_items, sources, errors = await _search_by_genres(resolved, mode)

        total = len(all_items)
        start = (page - 1) * limit
        page_items = all_items[start : start + limit]
        primary_source = "google_books" if "google_books" in sources else "open_library"

        result = {
            "source": primary_source,
            "sources": sorted(sources),
            "mode": mode,
            "genres": [g["label"] for g in resolved],
            "page": page,
            "limit": limit,
            "total": total,
            "results": page_items,
            "errors": errors,
        }
        _set_cache(cache_key, result)
        return result

    if not q or q.strip() == "":
        raise HTTPException(
            status_code=400,
            detail="Enviá 'q' (título/autor/ISBN) o uno o más géneros en 'genres'",
        )

    query = q.strip()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                GOOGLE_BOOKS_URL, params={"q": query, "maxResults": 20}
            )
            if response.status_code == 200:
                items = response.json().get("items", []) or []
                results = []
                for item in items:
                    norm = normalize_google_books(item)
                    if norm.get("title"):
                        results.append(norm)
                return {"source": "google_books", "total": len(results), "results": results}
    except Exception:
        pass

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                "https://openlibrary.org/search.json", params={"q": query, "limit": 20}
            )
            if response.status_code == 200:
                docs = response.json().get("docs", []) or []
                results = [r for r in normalize_open_library(docs) if r.get("title")]
                return {"source": "open_library", "total": len(results), "results": results}
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
        user_id=current_user.id,
    )
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return {"message": "Guardado en biblioteca", "item": {"id": db_item.id, "title": db_item.title}}
