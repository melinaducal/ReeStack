"""Recommendation engine for the ReeStack assistant.

Two rules drive this module:

1. **Nothing is invented.** Every suggestion must be returned by a real
   catalogue provider (Open Library, Google Books, TMDB, TVMaze, Wikipedia,
   iTunes or Crossref). The LLM, when configured, only proposes candidate
   titles that are then verified against those providers.
2. **No keys required.** Without ``LLM_API_KEY`` the engine still answers using
   a deterministic parser plus catalogue search.

The router stays thin; everything testable lives here as pure functions or
functions that receive an explicit database session.
"""

import asyncio
import json
import os
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Sequence, Tuple

import httpx
from sqlalchemy.orm import Session

from app.models import Comment, Item, User
from app.routers import catalog

MEDIA_TYPES = ("book", "movie", "series", "music", "paper")

TYPE_NOUNS = {
    "book": ("libro", "libros", "novela", "novelas", "cuento", "ensayo", "poesia", "book", "novel"),
    "movie": ("pelicula", "peliculas", "film", "films", "cine", "movie", "movies", "largometraje", "documental"),
    "series": ("serie", "series", "temporada", "show", "shows"),
    "music": ("musica", "album", "albumes", "disco", "discos", "cancion", "banda", "music"),
    "paper": ("paper", "papers", "articulo", "investigacion", "cientifico", "academico"),
}


@dataclass(frozen=True)
class Genre:
    key: str
    label: str
    query: str
    aliases: Tuple[str, ...]


GENRES: Tuple[Genre, ...] = (
    Genre("romance", "romance", "romance", ("romance", "romantico", "romantica", "romanticismo", "amor", "love story")),
    Genre("mystery", "misterio", "mystery", ("misterio", "misterios", "misteriosa", "enigma", "detective", "whodunit")),
    Genre("thriller", "suspenso", "thriller", ("thriller", "suspenso", "suspense", "policial", "noir", "intriga", "oscuro", "oscura", "dark")),
    Genre("scifi", "ciencia ficción", "science fiction", ("ciencia ficcion", "sci fi", "scifi", "futurista", "distopia", "distopico", "space opera")),
    Genre("fantasy", "fantasía", "fantasy", ("fantasia", "fantastico", "magia", "magico")),
    Genre("horror", "terror", "horror", ("terror", "horror", "miedo", "sobrenatural")),
    Genre("drama", "drama", "drama", ("drama", "dramatico", "dramatica")),
    Genre("comedy", "comedia", "comedy", ("comedia", "comico", "humor", "risa")),
    Genre("adventure", "aventura", "adventure", ("aventura", "aventuras", "epico", "epica")),
    Genre("historical", "histórico", "historical fiction", ("historica", "historico", "novela historica", "de epoca")),
    Genre("crime", "crimen", "crime", ("crimen", "criminal", "mafia", "asesinato", "homicidio")),
    Genre("biography", "biografía", "biography", ("biografia", "biografico", "memorias")),
    Genre("poetry", "poesía", "poetry", ("poesia", "poemas", "poetico")),
    Genre("youngadult", "juvenil", "young adult", ("juvenil", "young adult", "adolescentes")),
    Genre("selfhelp", "desarrollo personal", "self help", ("autoayuda", "desarrollo personal", "habitos")),
    Genre("musical", "musical", "musical", ("musical", "musicales")),
)

GENRE_BY_KEY = {genre.key: genre for genre in GENRES}

POSITIVE_ENDINGS = ("final feliz", "termina bien", "happy ending", "buen final")
SHORT_WORKS = ("corto", "corta", "cortito", "breve", "novela corta", "relato corto")
RECENT_WORKS = ("novedad", "novedades", "nuevo", "nueva", "reciente", "recientes", "ultimo", "ultima", "estreno")
CLASSIC_WORKS = ("clasico", "clasica", "antiguo", "antigua", "vintage", "de culto")

STOPWORDS = {
    "the", "a", "an", "of", "and", "for", "with", "to", "in", "on", "el", "la",
    "los", "las", "un", "una", "unos", "unas", "de", "del", "y", "o", "u", "con",
    "sin", "para", "por", "que", "quiero", "me", "mi", "mis", "al", "algo",
    "algun", "alguna", "recomenda", "recomendame", "recomiendas", "busco",
    "buscame", "dame", "necesito", "gustaria", "favor", "porfa",
}


def normalize(text: str) -> str:
    """Lowercase, strip accents and collapse whitespace."""
    decomposed = unicodedata.normalize("NFKD", str(text or ""))
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(stripped.lower().replace("-", " ").replace("_", " ").split())


def _contains_phrase(haystack: str, phrase: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])", haystack) is not None


# ---------------------------------------------------------------------------
# Request interpretation
# ---------------------------------------------------------------------------


@dataclass
class Intent:
    raw: str
    types: List[str] = field(default_factory=list)
    genres: List[str] = field(default_factory=list)
    constraints: Dict[str, bool] = field(default_factory=dict)
    similar_to: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "types": list(self.types),
            "genres": list(self.genres),
            "constraints": dict(self.constraints),
            "similar_to": self.similar_to,
        }


def detect_types(text: str) -> List[str]:
    haystack = normalize(text)
    found = []
    for media_type, nouns in TYPE_NOUNS.items():
        if any(_contains_phrase(haystack, normalize(noun)) for noun in nouns):
            found.append(media_type)
    # "novela negra" is a genre phrase, not an explicit format request, but
    # treating it as a book is still a reasonable reading.
    return found


def detect_genres(text: str) -> List[str]:
    haystack = normalize(text)
    return [
        genre.key
        for genre in GENRES
        if any(_contains_phrase(haystack, normalize(alias)) for alias in genre.aliases)
    ]


def _detect_similar_to(text: str) -> Optional[str]:
    match = re.search(
        r"(?:parecid[oa]s? a|similar(?:es)? a|al estilo de|como)\s+([^,.;!?]{2,60})",
        normalize(text),
    )
    if not match:
        return None
    candidate = match.group(1).strip()
    candidate = " ".join(word for word in candidate.split() if word not in STOPWORDS)
    return candidate or None


def parse_request(message: str, forced_type: Optional[str] = None) -> Intent:
    haystack = normalize(message)
    constraints = {
        "happy_ending": any(_contains_phrase(haystack, normalize(phrase)) for phrase in POSITIVE_ENDINGS),
        "short": any(_contains_phrase(haystack, normalize(phrase)) for phrase in SHORT_WORKS),
        "recent": any(_contains_phrase(haystack, normalize(phrase)) for phrase in RECENT_WORKS),
        "classic": any(_contains_phrase(haystack, normalize(phrase)) for phrase in CLASSIC_WORKS),
    }

    types = detect_types(message)
    if forced_type:
        types = [forced_type]
    # A single explicit type wins; several mentions keep the first two.
    types = [media_type for media_type in types if media_type in MEDIA_TYPES][:2]

    return Intent(
        raw=message,
        types=types,
        genres=detect_genres(message),
        constraints=constraints,
        similar_to=_detect_similar_to(message),
    )


# ---------------------------------------------------------------------------
# Taste profile
# ---------------------------------------------------------------------------


@dataclass
class TasteProfile:
    type_weights: Dict[str, float] = field(default_factory=dict)
    creator_weights: Dict[str, float] = field(default_factory=dict)
    creator_names: Dict[str, str] = field(default_factory=dict)
    creator_types: Dict[str, Dict[str, float]] = field(default_factory=dict)
    genre_weights: Dict[str, float] = field(default_factory=dict)
    genre_types: Dict[str, Dict[str, float]] = field(default_factory=dict)
    consumed_titles: set = field(default_factory=set)
    rated_count: int = 0
    average_rating: float = 0.0
    total_items: int = 0

    def top_types(self) -> List[str]:
        ordered = sorted(
            ((media_type, weight) for media_type, weight in self.type_weights.items() if weight > 0),
            key=lambda pair: pair[1],
            reverse=True,
        )
        return [media_type for media_type, _weight in ordered]

    def top_genres(self, limit: int = 4) -> List[str]:
        ordered = sorted(
            ((genre, weight) for genre, weight in self.genre_weights.items() if weight > 0),
            key=lambda pair: pair[1],
            reverse=True,
        )
        return [genre for genre, _weight in ordered[:limit]]

    def top_genres_for(self, media_type: str, limit: int = 2) -> List[str]:
        """Favourite genres restricted to one media type (book vs movie)."""
        by_type = self.genre_types.get(media_type) or {}
        ordered = sorted(
            ((genre, weight) for genre, weight in by_type.items() if weight > 0),
            key=lambda pair: pair[1],
            reverse=True,
        )
        return [genre for genre, _weight in ordered[:limit]]

    def top_creators(self, media_type: str, limit: int = 2) -> List[str]:
        scored = []
        for key, by_type in self.creator_types.items():
            weight = by_type.get(media_type)
            if weight and weight > 0:
                scored.append((key, weight))
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return [key for key, _weight in scored[:limit]]

    def creator_display(self, key: str) -> str:
        return self.creator_names.get(key, key.title())


def _genre_signals(text: str) -> List[str]:
    if not text:
        return []
    haystack = normalize(text)
    return [
        genre.key
        for genre in GENRES
        if any(_contains_phrase(haystack, normalize(alias)) for alias in genre.aliases)
    ]


def _add_genre_signals(
    weights: Dict[str, float],
    text: str,
    amount: float,
    by_type: Optional[Dict[str, Dict[str, float]]] = None,
    media_type: Optional[str] = None,
) -> None:
    for key in _genre_signals(text):
        weights[key] = weights.get(key, 0.0) + amount
        if by_type is not None and media_type:
            bucket = by_type.setdefault(media_type, {})
            bucket[key] = bucket.get(key, 0.0) + amount


def build_profile(db: Session, user: User) -> TasteProfile:
    profile = TasteProfile()
    items = db.query(Item).filter(Item.user_id == user.id).all()
    comments = db.query(Comment).filter(Comment.user_id == user.id).all()

    item_by_id = {item.id: item for item in items}
    missing_ids = {comment.item_id for comment in comments} - set(item_by_id)
    if missing_ids:
        for extra in db.query(Item).filter(Item.id.in_(missing_ids)).all():
            item_by_id[extra.id] = extra

    profile.total_items = len(items)
    ratings = []

    for item in items:
        rating = float(item.rating) if item.rating else None
        if rating is not None:
            ratings.append(rating)
            weight = rating
        else:
            # Library presence without a score is a weak positive signal.
            weight = 3.0 if item.thoughts else 1.5

        profile.consumed_titles.add(normalize(item.title))
        profile.type_weights[item.type] = profile.type_weights.get(item.type, 0.0) + weight

        if item.creator:
            key = normalize(item.creator)
            profile.creator_weights[key] = profile.creator_weights.get(key, 0.0) + weight
            profile.creator_names.setdefault(key, item.creator)
            by_type = profile.creator_types.setdefault(key, {})
            by_type[item.type] = by_type.get(item.type, 0.0) + weight

        signal = " ".join(filter(None, [item.thoughts, item.title]))
        _add_genre_signals(
            profile.genre_weights, signal, weight, profile.genre_types, item.type
        )

    for comment in comments:
        source_item = item_by_id.get(comment.item_id)
        if not source_item:
            continue
        rating = float(comment.rating) if comment.rating else None
        if rating is not None:
            ratings.append(rating)
            # Below 2.5 stars the review is a negative signal.
            weight = rating - 3.0
        else:
            weight = 0.5

        profile.consumed_titles.add(normalize(source_item.title))
        _add_genre_signals(
            profile.genre_weights,
            comment.content,
            weight,
            profile.genre_types,
            source_item.type,
        )
        _add_genre_signals(
            profile.genre_weights,
            source_item.title,
            weight * 0.5,
            profile.genre_types,
            source_item.type,
        )

        if source_item.creator:
            key = normalize(source_item.creator)
            profile.creator_weights[key] = profile.creator_weights.get(key, 0.0) + weight
            profile.creator_names.setdefault(key, source_item.creator)

    profile.rated_count = len(ratings)
    profile.average_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0.0
    return profile


# ---------------------------------------------------------------------------
# Candidate scoring
# ---------------------------------------------------------------------------


def candidate_genres(candidate: dict) -> List[str]:
    return _genre_signals(
        " ".join(
            filter(
                None,
                [
                    candidate.get("title"),
                    candidate.get("creator"),
                    candidate.get("description"),
                ],
            )
        )
    )


def score_candidate(
    candidate: dict,
    intent: Intent,
    profile: TasteProfile,
    position: int = 0,
) -> Tuple[float, List[str]]:
    score = max(0.0, 1.0 - position * 0.08)
    genres = candidate_genres(candidate)
    matched = [genre for genre in intent.genres if genre in genres]

    score += 3.0 * len(matched)

    for genre in genres:
        weight = profile.genre_weights.get(genre, 0.0)
        if weight > 0:
            score += min(weight, 8.0) * 0.2

    creator_key = normalize(candidate.get("creator"))
    if creator_key and creator_key in profile.creator_weights:
        score += 2.5 + min(max(profile.creator_weights[creator_key], 0.0), 6.0) * 0.4

    media_type = candidate.get("type")
    score += min(max(profile.type_weights.get(media_type, 0.0), 0.0), 12.0) * 0.1

    year = candidate.get("year")
    if intent.constraints.get("recent") and isinstance(year, int):
        score += 1.0 if year >= date.today().year - 5 else -0.75
    if intent.constraints.get("classic") and isinstance(year, int):
        score += 1.0 if year <= 1985 else -0.5

    if intent.similar_to:
        haystack = normalize(f"{candidate.get('title')} {candidate.get('creator')}")
        if normalize(intent.similar_to) in haystack:
            score += 1.0

    return score, matched


def build_reason(
    candidate: dict,
    matched: List[str],
    profile: TasteProfile,
    intent: Intent,
) -> str:
    parts = []
    if matched:
        labels = ", ".join(GENRE_BY_KEY[key].label for key in matched)
        parts.append(f"Coincide con tu pedido: {labels}.")

    creator_key = normalize(candidate.get("creator"))
    creator_weight = profile.creator_weights.get(creator_key, 0.0) if creator_key else 0.0
    if creator_key and creator_weight >= 4:
        parts.append(
            f"{profile.creator_display(creator_key)} es una referencia que ya puntuaste alto."
        )

    profile_overlap = [genre for genre in candidate_genres(candidate) if genre in profile.top_genres(6)]
    if profile_overlap and not matched:
        labels = ", ".join(GENRE_BY_KEY[key].label for key in profile_overlap[:2])
        parts.append(f"Se parece a lo que solés elegir ({labels}).")

    if intent.constraints.get("recent") and isinstance(candidate.get("year"), int):
        parts.append(f"Es reciente ({candidate['year']}).")

    if not parts:
        parts.append("Está en el catálogo y todavía no lo tenés en tu biblioteca.")

    return " ".join(parts)[:280]


# ---------------------------------------------------------------------------
# Catalogue helpers
# ---------------------------------------------------------------------------


def _genre_query(keys: Sequence[str]) -> str:
    return " ".join(GENRE_BY_KEY[key].query for key in keys)


def derive_search_queries(intent: Intent, profile: TasteProfile, media_type: str) -> List[str]:
    queries: List[str] = []

    if intent.genres:
        queries.append(_genre_query(intent.genres))
    if intent.similar_to:
        queries.append(intent.similar_to)

    for creator in profile.top_creators(media_type, limit=1):
        queries.append(profile.creator_display(creator))

    # "Algo parecido a X" still needs a genre anchor, otherwise the providers
    # only return X itself (which is already in the library).
    if not intent.genres:
        fallback = _genre_query(profile.top_genres_for(media_type, 2))
        if fallback:
            queries.append(fallback)

    if not queries:
        queries.append(_genre_query(profile.top_genres(2)) or "recomendados")

    unique: List[str] = []
    for query in queries:
        cleaned = " ".join(query.split())
        if len(cleaned) >= 2 and cleaned not in unique:
            unique.append(cleaned)
    return unique[:3]


async def _collect_for_type(
    intent: Intent,
    profile: TasteProfile,
    media_type: str,
    per_query: int,
) -> Tuple[List[dict], List[str]]:
    collected: List[dict] = []
    warnings: List[str] = []

    queries = derive_search_queries(intent, profile, media_type)
    for query in queries:
        results, _source, errors = await catalog.search_catalog_results(media_type, query)
        for error in errors:
            if error not in warnings:
                warnings.append(error)
        collected.extend(results[:per_query])

    # TMDB needs a key and TVMaze matches names rather than genres, so a
    # genre-only request can come back empty for films and series.
    if media_type in ("movie", "series"):
        has_tmdb = bool((os.getenv("TMDB_API_KEY") or "").strip())
        needs_fallback = not collected or (media_type == "movie" and not has_tmdb and len(collected) < 5)
        if needs_fallback:
            kind = "film" if media_type == "movie" else "television"
            # One anchor per detected genre finds more real titles than a
            # single joined query.
            anchors = [GENRE_BY_KEY[key].query for key in intent.genres]
            if not anchors and queries:
                anchors = [queries[-1]]
            for anchor in anchors[:2]:
                fallback, error = await _wikipedia_media(kind, anchor)
                if error:
                    warnings.append(error)
                collected.extend(fallback[:per_query])

    # Copy so the shared provider cache never gets mutated.
    return [dict(candidate, type=media_type) for candidate in collected], warnings


async def search_candidates(
    intent: Intent,
    profile: TasteProfile,
    types: Sequence[str],
    per_query: int = 12,
) -> Tuple[List[dict], List[str]]:
    tasks = [_collect_for_type(intent, profile, media_type, per_query) for media_type in types]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    candidates: List[dict] = []
    warnings: List[str] = []
    for outcome in results:
        if isinstance(outcome, Exception):
            warnings.append("catalog_search_failed")
            continue
        found, found_warnings = outcome
        candidates.extend(found)
        for warning in found_warnings:
            if warning not in warnings:
                warnings.append(warning)
    return candidates, warnings


_WIKIPEDIA_MEDIA = {
    "film": {
        "infobox": r"\{\{\s*infobox film\s*(?=[|\n}])",
        "suffix": "film",
        "creator": "director",
        "date": "released",
    },
    "television": {
        "infobox": r"\{\{\s*infobox television\s*(?=[|\n}])",
        "suffix": "television series",
        "creator": "creator",
        "date": "first_aired",
    },
}


async def _wikipedia_media(kind: str, query: str) -> Tuple[List[dict], Optional[str]]:
    """Keyless Wikipedia fallback for films and series.

    TMDB needs a key and TVMaze matches names rather than genres, so a
    genre-only request can come back empty. Wikipedia articles carry an
    infobox with director/creator, release date and poster.
    """
    config = _WIKIPEDIA_MEDIA.get(kind)
    if not config or not query:
        return [], None

    cache_key = f"wiki:{kind}:{normalize(query)}"
    cached = catalog._cache_get(cache_key)
    if cached is not None:
        return cached

    # Unquoted multi-word genres match the genre article itself
    # ("science fiction film" returns 1 film; '"science fiction" film' 12).
    term = f'"{query}"' if " " in query.strip() else query

    params_base = {"format": "json", "formatversion": 2}
    try:
        async with httpx.AsyncClient(
            timeout=20.0,
            headers={"User-Agent": catalog.USER_AGENT, "Accept": "application/json"},
        ) as client:
            search = await client.get(
                catalog.WIKIPEDIA_API_URL,
                params={
                    **params_base,
                    "action": "query",
                    "list": "search",
                    "srsearch": f"{term} {config['suffix']}",
                    "srlimit": 20,
                },
            )
            if search.status_code != 200:
                return [], f"wikipedia_status_{search.status_code}"
            hits = (search.json().get("query") or {}).get("search") or []
            titles = [hit.get("title") for hit in hits if hit.get("title")]
            if not titles:
                return [], None

            response = await client.get(
                catalog.WIKIPEDIA_API_URL,
                params={
                    **params_base,
                    "action": "query",
                    "titles": "|".join(titles[:20]),
                    "prop": "revisions|extracts",
                    "rvprop": "content",
                    "rvslots": "main",
                    "exintro": 1,
                    "explaintext": 1,
                    "exlimit": "max",
                    "redirects": 1,
                },
            )
            if response.status_code != 200:
                return [], f"wikipedia_status_{response.status_code}"
            pages = (response.json().get("query") or {}).get("pages") or []

            cover_files = {}
            for page in pages:
                revisions = page.get("revisions") or []
                slot = (revisions[0].get("slots") or {}).get("main") if revisions else None
                wikitext = (slot or {}).get("content") or ""
                if not re.search(config["infobox"], wikitext, re.IGNORECASE):
                    continue
                cover_files[page.get("title")] = catalog._file_name(
                    catalog._infobox_value(wikitext, "image") or ""
                )

            covers = {}
            file_titles = [f"File:{name}" for name in cover_files.values() if name]
            if file_titles:
                images = await client.get(
                    catalog.WIKIPEDIA_API_URL,
                    params={
                        **params_base,
                        "action": "query",
                        "titles": "|".join(dict.fromkeys(file_titles)),
                        "prop": "imageinfo",
                        "iiprop": "url",
                        "iiurlwidth": 400,
                    },
                )
                if images.status_code == 200:
                    for page in (images.json().get("query") or {}).get("pages") or []:
                        info = (page.get("imageinfo") or [{}])[0]
                        url = info.get("thumburl") or info.get("url")
                        if url:
                            covers[page.get("title")] = url.split("?")[0]
    except (httpx.HTTPError, ValueError):
        return [], "wikipedia_request_failed"

    tokens = [token for token in normalize(query).split() if len(token) > 2 and token not in STOPWORDS]
    scored = []
    for page in pages:
        revisions = page.get("revisions") or []
        slot = (revisions[0].get("slots") or {}).get("main") if revisions else None
        wikitext = (slot or {}).get("content") or ""
        if not re.search(config["infobox"], wikitext, re.IGNORECASE):
            continue

        title = page.get("title")
        if not title:
            continue
        extract = " ".join((page.get("extract") or "").split())
        haystack = normalize(f"{title} {extract}")
        # Lenient relevance: at least one query token must appear, so genre
        # searches still return real films instead of an empty list.
        hits_count = sum(1 for token in tokens if token in haystack)
        if tokens and hits_count == 0:
            continue

        file_name = cover_files.get(title)
        cover = covers.get(f"File:{file_name}") if file_name else None
        scored.append(
            (
                hits_count,
                {
                    "external_id": title,
                    "title": title,
                    "creator": catalog._clean_wiki(
                        catalog._infobox_value(wikitext, config["creator"]) or ""
                    )
                    or None,
                    "year": catalog._year(catalog._infobox_value(wikitext, config["date"]))
                    or catalog._year(extract),
                    "cover_url": cover,
                    "description": extract[:280] or None,
                    "source": "wikipedia",
                },
            )
        )

    scored.sort(key=lambda pair: pair[0], reverse=True)
    results = [item for _score, item in scored][:12]
    catalog._cache_set(cache_key, (results, None))
    return results, None


# ---------------------------------------------------------------------------
# LLM (optional)
# ---------------------------------------------------------------------------


def llm_settings() -> dict:
    return {
        "key": (os.getenv("LLM_API_KEY") or "").strip(),
        "url": os.getenv("LLM_API_URL", "https://openrouter.ai/api/v1/chat/completions"),
        "model": os.getenv("LLM_MODEL", "anthropic/claude-3.5-sonnet"),
        "app_name": os.getenv("LLM_APP_NAME", "ReeStack"),
        "app_url": os.getenv("LLM_APP_URL", "http://localhost:5173"),
        "timeout": float(os.getenv("LLM_TIMEOUT", "30") or 30),
    }


def build_llm_prompt(
    intent: Intent,
    profile: TasteProfile,
    history: Sequence[dict],
    limit: int,
    types: Sequence[str],
) -> List[dict]:
    top_genres = [GENRE_BY_KEY[key].label for key in profile.top_genres(5)]
    top_creators = [
        profile.creator_display(key)
        for key in sorted(profile.creator_weights, key=profile.creator_weights.get, reverse=True)[:5]
    ]
    library = sorted(profile.consumed_titles)[:40]
    history_text = "\n".join(
        f"{turn['role']}: {turn['content'][:300]}" for turn in history[-6:]
    ) or "(sin historial)"

    system = (
        "Sos el asistente de recomendaciones de ReeStack. Proponés obras concretas "
        "que ya existen. Nunca inventes títulos. Respondés solo JSON válido con la forma "
        '{"recommendations":[{"title":"...","type":"book|movie|series|music|paper",'
        '"creator":"...","reason":"..."}]}. '
        "El motivo debe ser una frase breve en español que conecte la obra con el pedido."
    )
    user = (
        f"Pedido del usuario: {intent.raw}\n"
        f"Tipos permitidos: {', '.join(types)}\n"
        f"Géneros detectados: {', '.join(intent.genres) or 'sin especificar'}\n"
        f"Restricciones: {json.dumps(intent.constraints, ensure_ascii=False)}\n"
        f"Obra de referencia: {intent.similar_to or 'ninguna'}\n"
        f"Géneros que suele elegir: {', '.join(top_genres) or 'sin datos'}\n"
        f"Autores o creadores que puntuó alto: {', '.join(top_creators) or 'sin datos'}\n"
        f"Promedio de puntuaciones: {profile.average_rating} ({profile.rated_count} notas)\n"
        f"Ya tiene en su biblioteca (no recomendar): {json.dumps(library, ensure_ascii=False)}\n"
        f"Historial de la conversación:\n{history_text}\n"
        f"Devolvé como máximo {limit} recomendaciones reales."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _extract_json(content: str) -> Optional[dict]:
    try:
        return json.loads(content)
    except (TypeError, ValueError):
        match = re.search(r"\{.*\}", content or "", re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group())
        except ValueError:
            return None


async def propose_titles(
    intent: Intent,
    profile: TasteProfile,
    history: Sequence[dict],
    limit: int,
    types: Sequence[str],
) -> Tuple[List[dict], List[str]]:
    settings = llm_settings()
    if not settings["key"]:
        return [], ["llm_key_missing"]

    messages = build_llm_prompt(intent, profile, history, limit, types)
    payload = {
        "model": settings["model"],
        "messages": messages,
        "temperature": 0.4,
    }

    try:
        async with httpx.AsyncClient(timeout=settings["timeout"]) as client:
            response = await client.post(
                settings["url"],
                headers={
                    "Authorization": f"Bearer {settings['key']}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": settings["app_url"],
                    "X-Title": settings["app_name"],
                },
                json=payload,
            )
    except httpx.TimeoutException:
        return [], ["llm_timeout"]
    except httpx.HTTPError:
        return [], ["llm_unavailable"]

    if response.status_code == 429:
        return [], ["llm_quota_exceeded"]
    if response.status_code in (401, 403):
        return [], ["llm_invalid_key"]
    if response.status_code >= 500:
        return [], ["llm_upstream_error"]
    if response.status_code != 200:
        return [], [f"llm_status_{response.status_code}"]

    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        return [], ["llm_invalid_response"]

    parsed = _extract_json(content)
    if not isinstance(parsed, dict):
        return [], ["llm_invalid_response"]

    proposals = []
    for item in parsed.get("recommendations") or []:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        proposals.append(
            {
                "title": title,
                "type": str(item.get("type") or "").strip().lower(),
                "creator": str(item.get("creator") or "").strip() or None,
                "reason": str(item.get("reason") or "").strip(),
            }
        )
    return proposals[:limit], []


def _titles_match(left: str, right: str) -> bool:
    a = normalize(left)
    b = normalize(right)
    if not a or not b:
        return False
    if a == b:
        return True
    # Allow subtitle differences such as "Dune" vs "Dune (novel)".
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    return len(shorter) >= 4 and shorter in longer


async def verify_proposals(
    proposals: Sequence[dict],
    types: Sequence[str],
    limit: int,
) -> Tuple[List[dict], List[str]]:
    """Keep only proposals that exist in a real catalogue."""
    verified: List[dict] = []
    warnings: List[str] = []
    discarded = 0

    for proposal in proposals:
        media_type = proposal.get("type")
        if media_type not in MEDIA_TYPES or media_type not in types:
            discarded += 1
            continue

        results, _source, errors = await catalog.search_catalog_results(
            media_type, proposal["title"]
        )
        for error in errors:
            if error not in warnings:
                warnings.append(error)

        match = None
        for result in results:
            if _titles_match(proposal["title"], result.get("title", "")):
                match = result
                break
        if not match:
            discarded += 1
            continue

        candidate = dict(match)
        candidate["type"] = media_type
        candidate["reason"] = proposal.get("reason") or ""
        verified.append(candidate)
        if len(verified) >= limit:
            break

    if discarded:
        warnings.append("llm_suggestions_not_in_catalog")
    return verified, warnings


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _dedupe_candidates(candidates: Sequence[dict]) -> List[dict]:
    seen = set()
    unique = []
    for candidate in candidates:
        key = (candidate.get("type"), normalize(candidate.get("title")))
        if key in seen or not candidate.get("title"):
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _describe_intent(intent: Intent, types: Sequence[str]) -> str:
    labels = {
        "book": "libros",
        "movie": "películas",
        "series": "series",
        "music": "música",
        "paper": "papers",
    }
    selected = [labels[media_type] for media_type in types if media_type in labels]
    if not selected:
        subject = "contenido"
    elif len(selected) == 1:
        subject = selected[0]
    else:
        subject = ", ".join(selected[:-1]) + f" y {selected[-1]}"

    text = subject
    if intent.genres:
        text += " de " + " y ".join(GENRE_BY_KEY[key].label for key in intent.genres)
    if intent.constraints.get("happy_ending"):
        text += " con final feliz"
    for flag, label in (("recent", "recientes"), ("classic", "clásicas"), ("short", "cortas")):
        if intent.constraints.get(flag):
            text += f" {label}"
    return text


async def recommend(
    db: Session,
    user: User,
    message: str,
    *,
    forced_type: Optional[str] = None,
    limit: int = 4,
    exclude_consumed: bool = True,
    exclude_titles: Optional[Sequence[str]] = None,
    history: Optional[Sequence[dict]] = None,
) -> dict:
    history = list(history or [])
    intent = parse_request(message, forced_type)
    profile = build_profile(db, user)

    types = list(intent.types)
    if not types:
        types = [media_type for media_type in profile.top_types() if media_type in MEDIA_TYPES][:2]
    if not types:
        types = ["book", "movie", "series"]
    types = [media_type for media_type in types if media_type in MEDIA_TYPES] or ["book"]

    settings = llm_settings()
    warnings: List[str] = []
    candidates: List[dict] = []
    engine = "heuristic"

    if settings["key"]:
        proposals, llm_warnings = await propose_titles(
            intent, profile, history, limit, types
        )
        warnings.extend(llm_warnings)
        if proposals:
            verified, verify_warnings = await verify_proposals(proposals, types, limit)
            warnings.extend(verify_warnings)
            if verified:
                candidates = verified
                engine = "llm"
        if engine != "llm" and not llm_warnings:
            warnings.append("llm_suggestions_unverified")
    else:
        warnings.append("llm_key_missing")

    if not candidates:
        searched, search_warnings = await search_candidates(intent, profile, types)
        warnings.extend(search_warnings)
        candidates = searched
        if engine == "llm":
            engine = "heuristic"

    if exclude_consumed:
        candidates = [
            candidate
            for candidate in candidates
            if normalize(candidate.get("title")) not in profile.consumed_titles
        ]

    # Titles already offered earlier in the same conversation.
    blocked = {normalize(title) for title in (exclude_titles or []) if title}
    if blocked:
        candidates = [
            candidate
            for candidate in candidates
            if normalize(candidate.get("title")) not in blocked
        ]

    candidates = _dedupe_candidates(candidates)

    scored = []
    for position, candidate in enumerate(candidates):
        score, matched = score_candidate(candidate, intent, profile, position)
        # When the user named genres, a candidate matching none of them is
        # only kept if nothing else came back.
        if intent.genres and not matched:
            score -= 2.0
        scored.append((score, matched, candidate))
    scored.sort(key=lambda row: row[0], reverse=True)

    selected = []
    for score, matched, candidate in scored:
        if len(selected) >= limit:
            break
        reason = candidate.get("reason") if engine == "llm" and candidate.get("reason") else None
        selected.append(
            {
                "title": candidate.get("title"),
                "type": candidate.get("type"),
                "creator": candidate.get("creator"),
                "year": candidate.get("year"),
                "cover_url": candidate.get("cover_url"),
                "external_id": candidate.get("external_id"),
                "source": candidate.get("source"),
                "reason": reason or build_reason(candidate, matched, profile, intent),
                "matched_genres": [GENRE_BY_KEY[key].label for key in matched],
                "in_library": normalize(candidate.get("title")) in profile.consumed_titles,
            }
        )

    deduped_warnings: List[str] = []
    for warning in warnings:
        if warning not in deduped_warnings:
            deduped_warnings.append(warning)

    subject = _describe_intent(intent, types)
    if selected:
        count = len(selected)
        noun = "opción" if count == 1 else "opciones"
        answer = f"Encontré {count} {noun} en el catálogo para {subject}."
    else:
        answer = (
            f"No encontré obras nuevas que encajen con {subject}. "
            "Probá con otro género o agregá la clave de TMDB para ampliar el catálogo."
        )

    return {
        "message": answer,
        "recommendations": selected,
        "engine": engine,
        "degraded": any(warning.startswith("llm_") for warning in deduped_warnings),
        "warnings": deduped_warnings,
        "intent": intent.to_dict(),
    }
