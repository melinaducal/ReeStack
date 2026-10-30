"""Real catalogue search for every media type.

The frontend used to fabricate results for anything that was not a book. This
module replaces that with provider-backed search, normalised into one shape:

    {external_id, title, creator, year, cover_url, description, source}

Providers are free and keyless except TMDB (optional, better movie posters).
An empty provider response is a valid 200 with an empty list, never a 503.
"""

import html
import os
import re
import time
import unicodedata
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.deps import get_current_user
from app.models import User

router = APIRouter(prefix="/catalog", tags=["catalog"])

SUPPORTED_TYPES = {"book", "movie", "series", "music", "paper"}

OPEN_LIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"
ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
MUSICBRAINZ_RELEASE_URL = "https://musicbrainz.org/ws/2/release"
COVER_ART_ARCHIVE_URL = "https://coverartarchive.org/release/{mbid}/front-500"
TVMAZE_SEARCH_URL = "https://api.tvmaze.com/search/shows"
WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/movie"
TMDB_IMAGE_URL = "https://image.tmdb.org/t/p/w500{path}"
CROSSREF_WORKS_URL = "https://api.crossref.org/works"

USER_AGENT = "ReeStack/1.0 (contact: dev@reestack.local)"

# Providers cap how many rows they return; the endpoint paginates that snapshot.
PROVIDER_LIMIT = 50

_CACHE_TTL = 300
_cache = {}


def _cache_get(key):
    entry = _cache.get(key)
    if not entry:
        return None
    expires_at, payload = entry
    if expires_at < time.time():
        _cache.pop(key, None)
        return None
    return payload


def _cache_set(key, payload):
    _cache[key] = (time.time() + _CACHE_TTL, payload)


def _norm_text(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = text.lower().replace("-", " ").replace("_", " ")
    return " ".join(text.split())


def _clean_html(value) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", str(value or "")))
    return " ".join(text.split())


def _clean_wiki(value: str) -> str:
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", value or "", flags=re.IGNORECASE)
    text = re.sub(r"<ref[^>]*/>", "", text)
    text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    text = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"'{2,}", "", text)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    # Leftovers from multi-line templates such as {{Plainlist| ... }}
    text = re.sub(r"\b(?:plainlist|ubl|unbulleted list|flatlist|hlist)\b", "", text, flags=re.IGNORECASE)
    text = text.replace("{{", "").replace("}}", "").replace("|", " ")
    lines = [
        " ".join(line.strip(" *;,").split())
        for line in text.splitlines()
        if line.strip(" *;,")
    ]
    return ", ".join(lines).strip(" ,;")


def _year(value) -> Optional[int]:
    match = re.search(r"(1[89]\d{2}|20\d{2})", str(value or ""))
    return int(match.group(1)) if match else None


def _dedupe(results: List[dict]) -> List[dict]:
    seen = set()
    unique = []
    for item in results:
        if not item or not item.get("title"):
            continue
        key = item.get("external_id")
        if not key:
            key = "{}|{}".format(
                _norm_text(item.get("title")), _norm_text(item.get("creator"))
            )
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


# ---------------------------------------------------------------------------
# Normalisers (pure functions, unit-testable)
# ---------------------------------------------------------------------------


def _normalize_open_library_doc(doc: dict) -> Optional[dict]:
    title = doc.get("title")
    if not title:
        return None
    cover_id = doc.get("cover_i")
    return {
        "external_id": doc.get("key"),
        "title": title,
        "creator": ", ".join(doc.get("author_name") or []) or None,
        "year": doc.get("first_publish_year"),
        "cover_url": (
            f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"
            if cover_id
            else None
        ),
        "description": None,
        "source": "open_library",
    }


def _normalize_itunes_album(item: dict) -> Optional[dict]:
    title = item.get("collectionName") or item.get("trackName")
    if not title:
        return None
    artwork = item.get("artworkUrl100")
    if artwork:
        # iTunes serves the same art at higher resolution.
        artwork = artwork.replace("100x100bb", "600x600bb")
    return {
        "external_id": str(item.get("collectionId") or item.get("trackId") or ""),
        "title": title,
        "creator": item.get("artistName") or None,
        "year": _year(item.get("releaseDate")),
        "cover_url": artwork or None,
        "description": item.get("primaryGenreName") or None,
        "source": "itunes",
    }


def _normalize_musicbrainz_release(release: dict) -> Optional[dict]:
    title = release.get("title")
    if not title:
        return None
    credits = release.get("artist-credit") or []
    artists = []
    for credit in credits:
        if isinstance(credit, dict):
            name = credit.get("name") or (credit.get("artist") or {}).get("name")
            if name:
                artists.append(name)
    release_id = release.get("id")
    return {
        "external_id": release_id,
        "title": title,
        "creator": ", ".join(artists) or None,
        "year": _year(release.get("date")),
        "cover_url": (
            COVER_ART_ARCHIVE_URL.format(mbid=release_id) if release_id else None
        ),
        "description": None,
        "source": "musicbrainz",
    }


def _normalize_tvmaze_show(show: dict) -> Optional[dict]:
    title = show.get("name")
    if not title:
        return None
    image = show.get("image") or {}
    genres = show.get("genres") or []
    return {
        "external_id": str(show.get("id") or ""),
        "title": title,
        "creator": None,
        "year": _year(show.get("premiered")),
        "cover_url": image.get("original") or image.get("medium"),
        "description": ", ".join(genres) or None,
        "source": "tvmaze",
    }


def _normalize_tmdb_movie(movie: dict) -> Optional[dict]:
    title = movie.get("title") or movie.get("original_title")
    if not title:
        return None
    poster = movie.get("poster_path")
    return {
        "external_id": str(movie.get("id") or ""),
        "title": title,
        "creator": None,
        "year": _year(movie.get("release_date")),
        "cover_url": TMDB_IMAGE_URL.format(path=poster) if poster else None,
        "description": movie.get("overview") or None,
        "source": "tmdb",
    }


def _normalize_crossref_item(item: dict) -> Optional[dict]:
    titles = item.get("title") or []
    title = _clean_html(titles[0]) if titles else None
    if not title:
        return None
    authors = []
    for author in item.get("author") or []:
        name = " ".join(
            part for part in [author.get("given"), author.get("family")] if part
        )
        if name:
            authors.append(name)
    issued = (item.get("issued") or {}).get("date-parts") or []
    year = issued[0][0] if issued and issued[0] else None
    container = item.get("container-title") or []
    return {
        "external_id": item.get("DOI"),
        "title": title,
        "creator": ", ".join(authors) or None,
        "year": year,
        "cover_url": None,
        "description": _clean_html(container[0]) if container else item.get("type"),
        "source": "crossref",
    }


def _infobox_value(wikitext: str, field: str) -> Optional[str]:
    # Values may span several lines ({{Plainlist| ... }}), so stop at the next
    # infobox field or at the end of the template.
    match = re.search(
        r"^\s*\|\s*"
        + re.escape(field)
        + r"\s*=\s*(.+?)(?=^\s*\|\s*[A-Za-z_][A-Za-z0-9_ ]*\s*=|\n\}\})",
        wikitext,
        flags=re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    return match.group(1).strip() if match else None


def _file_name(value: str) -> Optional[str]:
    if not value:
        return None
    match = re.search(
        r"(?:File:|Image:)?([^|\]\n]+?\.(?:jpe?g|png|webp|gif))", value, re.IGNORECASE
    )
    return match.group(1).strip() if match else None


def _normalize_wikipedia_film(
    title: str, wikitext: str, cover_url: Optional[str], extract: str = ""
):
    # Require an actual film infobox, not an awards/list page that merely
    # mentions films ("infobox award" pages also contain the word "film").
    if not re.search(r"\{\{\s*infobox film\s*(?=[|\n}])", wikitext, re.IGNORECASE):
        return None
    director = _clean_wiki(_infobox_value(wikitext, "director") or "") or None
    released = _infobox_value(wikitext, "released")
    summary = " ".join((extract or "").split())
    return {
        "external_id": title,
        "title": title,
        "creator": director,
        "year": _year(released) or _year(summary),
        "cover_url": cover_url,
        "description": summary[:280] or None,
        "source": "wikipedia",
    }


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


async def _search_books(client, query: str, errors: List[str]):
    try:
        response = await client.get(
            OPEN_LIBRARY_SEARCH_URL, params={"q": query, "limit": PROVIDER_LIMIT}
        )
    except httpx.HTTPError:
        errors.append("open_library_request_failed")
        return [], None

    if response.status_code != 200:
        errors.append(f"open_library_status_{response.status_code}")
        return [], None

    try:
        docs = response.json().get("docs") or []
    except ValueError:
        errors.append("open_library_invalid_json")
        return [], None

    results = [r for r in (_normalize_open_library_doc(d) for d in docs) if r]
    return results, "open_library"


async def _search_music(client, query: str, errors: List[str]):
    """iTunes first (best artwork), MusicBrainz + Cover Art Archive as fallback."""
    try:
        response = await client.get(
            ITUNES_SEARCH_URL,
            params={
                "term": query,
                "media": "music",
                "entity": "album",
                "limit": PROVIDER_LIMIT,
            },
        )
        if response.status_code == 200:
            try:
                items = response.json().get("results") or []
            except ValueError:
                items = []
                errors.append("itunes_invalid_json")
            results = [r for r in (_normalize_itunes_album(i) for i in items) if r]
            if results:
                return results, "itunes"
        else:
            errors.append(f"itunes_status_{response.status_code}")
    except httpx.HTTPError:
        errors.append("itunes_request_failed")

    safe_query = query.replace('"', " ").strip()
    try:
        response = await client.get(
            MUSICBRAINZ_RELEASE_URL,
            params={
                "query": f'release:"{safe_query}"',
                "fmt": "json",
                "limit": PROVIDER_LIMIT,
            },
        )
    except httpx.HTTPError:
        errors.append("musicbrainz_request_failed")
        return [], None

    if response.status_code != 200:
        errors.append(f"musicbrainz_status_{response.status_code}")
        return [], None

    try:
        releases = response.json().get("releases") or []
    except ValueError:
        errors.append("musicbrainz_invalid_json")
        return [], None

    results = [r for r in (_normalize_musicbrainz_release(x) for x in releases) if r]
    return results, "musicbrainz" if results else None


async def _search_series(client, query: str, errors: List[str]):
    try:
        response = await client.get(TVMAZE_SEARCH_URL, params={"q": query})
    except httpx.HTTPError:
        errors.append("tvmaze_request_failed")
        return [], None

    if response.status_code != 200:
        errors.append(f"tvmaze_status_{response.status_code}")
        return [], None

    try:
        items = response.json() or []
    except ValueError:
        errors.append("tvmaze_invalid_json")
        return [], None

    results = []
    for item in items:
        show = item.get("show") if isinstance(item, dict) else None
        normalized = _normalize_tvmaze_show(show) if show else None
        if normalized:
            results.append(normalized)
    return results[:PROVIDER_LIMIT], "tvmaze" if results else None


async def _wikipedia_films(client, query: str, errors: List[str]):
    search_query = query
    if not re.search(r"\b(film|movie|pel[ií]cula)\b", query, re.IGNORECASE):
        search_query = f"{query} film"

    try:
        search = await client.get(
            WIKIPEDIA_API_URL,
            params={
                "action": "query",
                "list": "search",
                "srsearch": search_query,
                # TextExtracts caps extracts at 20 pages per request.
                "srlimit": 20,
                "format": "json",
                "formatversion": 2,
            },
        )
        if search.status_code != 200:
            errors.append(f"wikipedia_status_{search.status_code}")
            return [], None
        hits = (search.json().get("query") or {}).get("search") or []
    except (httpx.HTTPError, ValueError):
        errors.append("wikipedia_search_failed")
        return [], None

    titles = [hit.get("title") for hit in hits if hit.get("title")]
    if not titles:
        return [], None

    pages = []
    # TextExtracts returns at most 20 extracts per batch.
    for start in range(0, len(titles), 20):
        batch = titles[start : start + 20]
        try:
            response = await client.get(
                WIKIPEDIA_API_URL,
                params={
                    "action": "query",
                    "titles": "|".join(batch),
                    "prop": "revisions|extracts",
                    "rvprop": "content",
                    "rvslots": "main",
                    "exintro": 1,
                    "explaintext": 1,
                    "exlimit": "max",
                    "redirects": 1,
                    "format": "json",
                    "formatversion": 2,
                },
            )
            if response.status_code != 200:
                errors.append(f"wikipedia_revisions_status_{response.status_code}")
                continue
            pages.extend((response.json().get("query") or {}).get("pages") or [])
        except (httpx.HTTPError, ValueError):
            errors.append("wikipedia_revisions_failed")

    parsed = []
    cover_files = {}
    for page in pages:
        revisions = page.get("revisions") or []
        slot = (revisions[0].get("slots") or {}).get("main") if revisions else None
        wikitext = (slot or {}).get("content") or ""
        if not wikitext:
            continue
        title = page.get("title")
        cover = _file_name(_infobox_value(wikitext, "image") or "")
        cover_files[title] = cover
        parsed.append((title, wikitext, page.get("extract") or ""))

    # One batch request resolves every poster thumbnail.
    covers = {}
    file_titles = [f"File:{name}" for name in cover_files.values() if name]
    if file_titles:
        try:
            response = await client.get(
                WIKIPEDIA_API_URL,
                params={
                    "action": "query",
                    "titles": "|".join(dict.fromkeys(file_titles)),
                    "prop": "imageinfo",
                    "iiprop": "url",
                    "iiurlwidth": 400,
                    "format": "json",
                    "formatversion": 2,
                },
            )
            if response.status_code == 200:
                for page in (response.json().get("query") or {}).get("pages") or []:
                    info = (page.get("imageinfo") or [{}])[0]
                    url = info.get("thumburl") or info.get("url")
                    if url:
                        covers[page.get("title")] = url.split("?")[0]
            else:
                errors.append(f"wikipedia_imageinfo_status_{response.status_code}")
        except (httpx.HTTPError, ValueError):
            errors.append("wikipedia_imageinfo_failed")

    # Search ranking is noisy ("Inception film" can match another film's plot).
    # Keep only pages whose title or intro actually mentions the query, and put
    # exact title matches first.
    query_norm = _norm_text(query)
    stopwords = {
        "the", "a", "an", "of", "and", "el", "la", "los", "las",
        "de", "del", "y", "un", "una", "al",
    }
    tokens = [t for t in query_norm.split() if len(t) > 2 and t not in stopwords]

    def _mentions_query(page):
        title, _wikitext, extract = page
        haystack = _norm_text(f"{title} {extract}")
        if not tokens:
            return query_norm in haystack
        return all(token in haystack for token in tokens)

    relevant = [page for page in parsed if _mentions_query(page)]
    if relevant:
        parsed = relevant

    def _relevance(page):
        title, _wikitext, extract = page
        title_norm = _norm_text(title)
        if title_norm == query_norm:
            return 0
        if query_norm in title_norm:
            return 1
        # Translated titles usually appear in the first sentence:
        # "The Secret in Their Eyes (Spanish: El secreto de sus ojos)".
        if query_norm in _norm_text(extract[:400]):
            return 2
        return 3

    parsed.sort(key=_relevance)

    results = []
    for title, wikitext, extract in parsed:
        name = cover_files.get(title)
        cover = covers.get(f"File:{name}") if name else None
        normalized = _normalize_wikipedia_film(title, wikitext, cover, extract)
        if normalized:
            results.append(normalized)

    return results[:PROVIDER_LIMIT], "wikipedia" if results else None


async def _search_movies(client, query: str, errors: List[str]):
    api_key = (os.getenv("TMDB_API_KEY") or "").strip()
    if api_key:
        try:
            response = await client.get(
                TMDB_SEARCH_URL,
                params={
                    "api_key": api_key,
                    "query": query,
                    "language": "es-AR",
                    "include_adult": "false",
                    "page": 1,
                },
            )
            if response.status_code == 200:
                movies = response.json().get("results") or []
                results = [r for r in (_normalize_tmdb_movie(m) for m in movies) if r]
                if results:
                    return results, "tmdb"
            else:
                errors.append(f"tmdb_status_{response.status_code}")
        except (httpx.HTTPError, ValueError):
            errors.append("tmdb_request_failed")

    return await _wikipedia_films(client, query, errors)


async def _search_papers(client, query: str, errors: List[str]):
    try:
        response = await client.get(
            CROSSREF_WORKS_URL,
            params={
                "query.bibliographic": query,
                "rows": PROVIDER_LIMIT,
                "select": "DOI,title,author,issued,container-title,type",
            },
        )
    except httpx.HTTPError:
        errors.append("crossref_request_failed")
        return [], None

    if response.status_code != 200:
        errors.append(f"crossref_status_{response.status_code}")
        return [], None

    try:
        items = (response.json().get("message") or {}).get("items") or []
    except ValueError:
        errors.append("crossref_invalid_json")
        return [], None

    results = [r for r in (_normalize_crossref_item(i) for i in items) if r]
    return results, "crossref" if results else None


_PROVIDERS = {
    "book": _search_books,
    "movie": _search_movies,
    "series": _search_series,
    "music": _search_music,
    "paper": _search_papers,
}


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/search")
async def search_catalog(
    q: str = "",
    type_: str = Query(..., alias="type"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
):
    media_type = (type_ or "").strip().lower()
    if media_type not in SUPPORTED_TYPES:
        raise HTTPException(
            status_code=400,
            detail="type debe ser book, movie, series, music o paper",
        )

    query = (q or "").strip()
    if len(query) < 2:
        raise HTTPException(status_code=400, detail="Enviá 'q' con al menos 2 caracteres")

    cache_key = f"{media_type}:{_norm_text(query)}"
    cached = _cache_get(cache_key)
    if cached is not None:
        results, source, errors = cached
    else:
        errors = []
        try:
            async with httpx.AsyncClient(
                timeout=25.0,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            ) as client:
                results, source = await _PROVIDERS[media_type](client, query, errors)
        except (httpx.HTTPError, ValueError):
            results, source = [], None
            errors = [f"{media_type}_provider_failed"]

        results = _dedupe(results)
        _cache_set(cache_key, (results, source, errors))

    total = len(results)
    start = (page - 1) * limit
    page_items = results[start : start + limit]

    return {
        "type": media_type,
        "query": query,
        "source": source,
        "sources": sorted({item.get("source") for item in results if item.get("source")}),
        "page": page,
        "limit": limit,
        "total": total,
        "results": page_items,
        "errors": errors,
    }
