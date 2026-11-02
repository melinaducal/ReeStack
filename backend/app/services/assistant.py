"""Contextual conversation layer for the ReeStack assistant.

``recommender`` answers "what should I read/watch". This module answers
"what did you mean" and "what about the ones you already showed me".

Responsibilities:

* Rebuild the conversation state from persisted turns, including the works
  recommended in each turn (not just the plain text summary).
* Classify the user's intent. The LLM is the primary interpreter; a
  context-aware fallback keeps the feature working without an API key.
* Resolve references such as "el segundo", "el último" or "ese libro" against
  the real works of the conversation.
* Answer questions about already-recommended works with catalogue data only.
  No synopsis, author or plot is ever invented.
* Keep spoiler handling explicit.
"""

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import httpx

from app.routers import catalog
from app.services import recommender

ACTIONS = ("recommend", "details", "compare", "more", "refine", "chat", "spoiler")
MAX_CONTEXT_TURNS = 12

OPEN_LIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"
OPEN_LIBRARY_WORK_URL = "https://openlibrary.org{key}.json"
TMDB_DETAIL_URL = "https://api.themoviedb.org/3/{kind}/{external_id}"
TVMAZE_SHOW_URL = "https://api.tvmaze.com/shows/{external_id}"

ORDINALS = {
    "primer": 1,
    "primero": 1,
    "primera": 1,
    "segundo": 2,
    "segunda": 2,
    "tercero": 3,
    "tercera": 3,
    "tercer": 3,
    "cuarto": 4,
    "cuarta": 4,
    "quinto": 5,
    "quinta": 5,
    "sexto": 6,
    "sexta": 6,
}

SPOILER_OFF = (
    "sin spoiler",
    "sin spoilers",
    "no spoiler",
    "no spoilers",
    "no me cuentes el final",
    "no me spoilees",
    "sin adelantos",
)
SPOILER_ON = (
    "con spoiler",
    "con spoilers",
    "si spoiler",
    "si spoilers",
    "contame el final",
    "contame todo",
    "dalo todo",
)


# ---------------------------------------------------------------------------
# Conversation state
# ---------------------------------------------------------------------------


@dataclass
class Work:
    """One work that appeared in the conversation."""

    title: str
    type: str
    creator: Optional[str] = None
    year: Optional[int] = None
    external_id: Optional[str] = None
    source: Optional[str] = None
    description: Optional[str] = None
    reason: str = ""
    matched_genres: List[str] = field(default_factory=list)
    pages: Optional[int] = None
    runtime: Optional[int] = None
    cover_url: Optional[str] = None
    in_library: bool = False

    @property
    def key(self) -> Tuple[str, str]:
        return (self.type, recommender.normalize(self.title))

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Work":
        pages = data.get("pages")
        runtime = data.get("runtime")
        try:
            pages = int(pages) if pages is not None else None
        except (TypeError, ValueError):
            pages = None
        try:
            runtime = int(runtime) if runtime is not None else None
        except (TypeError, ValueError):
            runtime = None
        return cls(
            title=str(data.get("title") or "").strip(),
            type=str(data.get("type") or "").strip().lower(),
            creator=(str(data.get("creator")).strip() or None) if data.get("creator") else None,
            year=data.get("year") if isinstance(data.get("year"), int) else None,
            external_id=(str(data.get("external_id")) if data.get("external_id") is not None else None),
            source=data.get("source"),
            description=data.get("description"),
            reason=str(data.get("reason") or ""),
            matched_genres=list(data.get("matched_genres") or []),
            pages=pages,
            runtime=runtime,
            cover_url=data.get("cover_url"),
            in_library=bool(data.get("in_library")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "type": self.type,
            "creator": self.creator,
            "year": self.year,
            "external_id": self.external_id,
            "source": self.source,
            "description": self.description,
            "reason": self.reason,
            "matched_genres": list(self.matched_genres),
            "pages": self.pages,
            "runtime": self.runtime,
            "cover_url": self.cover_url,
            "in_library": self.in_library,
        }


@dataclass
class ConversationContext:
    works: List[Work] = field(default_factory=list)
    last_batch: List[Work] = field(default_factory=list)
    last_focus: List[Work] = field(default_factory=list)
    history: List[Dict[str, Any]] = field(default_factory=list)
    spoilers_allowed: bool = True

    def all_titles(self) -> List[str]:
        return [work.title for work in self.works if work.title]

    def indexed(self) -> List[Work]:
        return self.last_batch or self.works


def parse_stored_recommendations(raw: Optional[str]) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """Read the JSON stored in ``ChatTurn.recommendations``.

    New turns use ``{"kind": "<action>", "works": [...]}``. Older turns stored a
    plain list, so both shapes must keep working.
    """
    if not raw:
        return None, []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None, []
    if isinstance(data, list):
        return None, [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        kind = data.get("kind")
        works = data.get("works")
        if isinstance(works, list):
            return (str(kind) if kind else None), [item for item in works if isinstance(item, dict)]
    return None, []


def _spoiler_preference(text: str, current: bool) -> bool:
    haystack = recommender.normalize(text)
    if any(phrase in haystack for phrase in SPOILER_OFF):
        return False
    if any(phrase in haystack for phrase in SPOILER_ON):
        return True
    return current


def _only_spoiler_preference(message: str) -> Optional[bool]:
    """Detect a message that only changes the spoiler policy.

    Those turns deserve a short acknowledgement instead of a generic reply.
    """
    haystack = recommender.normalize(message).strip(" .!¡?¿")
    if haystack in ("sin spoilers", "sin spoiler", "no spoilers", "no spoiler"):
        return False
    if haystack in ("con spoilers", "con spoiler", "si spoilers", "si spoiler"):
        return True
    return None


def build_context(turns: Sequence[Any]) -> ConversationContext:
    """Reconstruct the contextual state from persisted turns."""
    context = ConversationContext()
    seen = set()

    for turn in turns:
        kind = None
        works: List[Work] = []
        if getattr(turn, "role", None) == "assistant":
            kind, payload = parse_stored_recommendations(getattr(turn, "recommendations", None))
            works = [Work.from_dict(item) for item in payload if item.get("title")]

        content = getattr(turn, "content", "") or ""
        context.history.append(
            {
                "role": getattr(turn, "role", "user"),
                "content": content,
                "works": [work.title for work in works],
            }
        )

        # Only the user's own messages define the spoiler preference. An
        # assistant warning must never flip it.
        if getattr(turn, "role", None) == "user":
            context.spoilers_allowed = _spoiler_preference(content, context.spoilers_allowed)

        if works:
            context.last_focus = works
            # Older turns have kind=None but were recommendation batches.
            if kind in (None, "recommend", "more", "refine"):
                context.last_batch = works
            for work in works:
                if work.key not in seen:
                    seen.add(work.key)
                    context.works.append(work)

    return context


# ---------------------------------------------------------------------------
# Reference resolution
# ---------------------------------------------------------------------------


def _has_word(haystack: str, word: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(word) + r"(?![a-z0-9])", haystack) is not None


def _unique_works(works: Sequence[Work]) -> List[Work]:
    seen = set()
    unique = []
    for work in works:
        if work.key in seen:
            continue
        seen.add(work.key)
        unique.append(work)
    return unique


def resolve_targets(message: str, context: ConversationContext) -> List[Work]:
    """Resolve "el primero", "la segunda", "el último", "ese libro"...

    Ordinals always refer to the last batch of recommendations, not to the
    accumulated history. That way asking about "el segundo" after a detail
    question still points at the original list.
    """
    haystack = recommender.normalize(message)
    pool = context.last_batch or context.works
    if not pool:
        return []

    # 1. Explicit title mention wins over any pronoun.
    mentioned = [
        work
        for work in context.works
        if len(recommender.normalize(work.title)) >= 4
        and recommender.normalize(work.title) in haystack
    ]
    if mentioned:
        mentioned.sort(key=lambda work: len(work.title), reverse=True)
        return [mentioned[0]]

    # 2. Ordinals.
    found = []
    for word, index in ORDINALS.items():
        if _has_word(haystack, word) and 0 < index <= len(pool):
            found.append(pool[index - 1])
    if found:
        return _unique_works(found)

    # 3. Last one.
    if any(_has_word(haystack, word) for word in ("ultimo", "ultima", "last")):
        return [pool[-1]]

    # 4. All of them.
    if any(
        phrase in haystack
        for phrase in (
            "los tres",
            "las tres",
            "los 3",
            "las 3",
            "los dos",
            "las dos",
            "todos",
            "todas",
            "ambos",
            "ambas",
        )
    ):
        return list(pool)

    # 5. Demonstratives: "ese libro", "esa película", "el de García Márquez".
    if any(_has_word(haystack, word) for word in ("ese", "esa", "este", "esta", "aquel", "aquella")):
        focus = context.last_focus or pool
        for media_type, nouns in recommender.TYPE_NOUNS.items():
            if any(_has_word(haystack, recommender.normalize(noun)) for noun in nouns):
                typed = [work for work in focus if work.type == media_type]
                if typed:
                    return [typed[-1]]
        return [focus[-1]]

    return []


# ---------------------------------------------------------------------------
# Intent detection (context-aware fallback)
# ---------------------------------------------------------------------------


def _looks_like_recommendation_request(haystack: str) -> bool:
    triggers = (
        "recomend",
        "recomiend",
        "sugeri",
        "sugiere",
        "que leo",
        "que puedo leer",
        "que veo",
        "que puedo ver",
        "buscame",
        "dame",
        "quiero",
        "necesito",
        "algo de",
        "opciones",
    )
    return any(trigger in haystack for trigger in triggers)


def _asks_spoiler(haystack: str) -> bool:
    return any(
        _has_word(haystack, word)
        for word in ("final", "termina", "termino", "desenlace", "spoiler", "spoilers", "muerte", "asesino")
    )


def _asks_compare(haystack: str) -> bool:
    comparison = (
        "cual de",
        "cual es",
        "cuales",
        "compara",
        "comparar",
        "comparacion",
        "diferencia",
        "mas corto",
        "mas corta",
        "mas largo",
        "mas larga",
        "mas viejo",
        "mas vieja",
        "mas nuevo",
        "mas nueva",
        "mas antiguo",
        "mas antigua",
        "mejor de",
    )
    return any(phrase in haystack for phrase in comparison)


def _asks_details(haystack: str) -> bool:
    triggers = (
        "de que trata",
        "de que se trata",
        "de que va",
        "sobre que trata",
        "sinopsis",
        "argumento",
        "resumen",
        "contame de",
        "quien escribio",
        "quien lo escribio",
        "quien es el autor",
        "quien es la autora",
        "autor",
        "autora",
        "director",
        "directora",
        "cuantas paginas",
        "cuantos minutos",
        "duracion",
        "de que ano",
        "que ano",
    )
    return any(trigger in haystack for trigger in triggers)


def _asks_more(haystack: str) -> bool:
    triggers = (
        "otros",
        "otras",
        "otro",
        "otra",
        "mas opciones",
        "mas recomendaciones",
        "dame mas",
        "siguiente",
        "parecid",
        "similar",
    )
    return any(trigger in haystack for trigger in triggers)


def _asks_refine(haystack: str) -> bool:
    triggers = (
        "pero ",
        "mejor ",
        "que sean",
        "prefiero",
        "cambia",
        "en vez de",
        "en lugar de",
        "mas cortos",
        "mas cortas",
        "mas recientes",
        "menos ",
        "sin ",
    )
    return any(trigger in haystack for trigger in triggers)


def heuristic_decision(message: str, context: ConversationContext) -> Dict[str, Any]:
    """Context-aware fallback used when the LLM is unavailable.

    It is not a fixed reply: it combines the persisted works, the reference
    resolver and the conversation's latest focus.
    """
    haystack = recommender.normalize(message)
    pool = context.last_batch or context.works
    targets = resolve_targets(message, context)
    action = "chat"
    only_preference = haystack.strip() in (
        "sin spoilers",
        "sin spoiler",
        "no spoilers",
        "con spoilers",
        "con spoiler",
    )

    if not pool:
        action = "recommend" if _looks_like_recommendation_request(haystack) else "chat"
    elif only_preference:
        action = "chat"
    elif _asks_spoiler(haystack):
        action = "spoiler"
    elif _asks_compare(haystack) and len(pool) > 1:
        action = "compare"
    elif _asks_details(haystack):
        action = "details"
    elif _asks_more(haystack):
        action = "more"
    elif _asks_refine(haystack) and (_looks_like_recommendation_request(haystack) or targets):
        action = "refine"
    elif targets:
        action = "details"
    elif _looks_like_recommendation_request(haystack):
        action = "recommend"

    if action in ("details", "compare", "spoiler") and not targets:
        targets = context.last_focus[-1:] or pool[-1:]
    if action in ("details", "compare", "spoiler") and not targets:
        action = "chat"

    return {
        "action": action,
        "targets": [work.title for work in targets],
        "spoilers": context.spoilers_allowed,
        "reply": "",
        "query": "",
    }


def _targets_by_title(titles: Sequence[str], pool: Sequence[Work]) -> List[Work]:
    normalized = {recommender.normalize(title): title for title in titles if title}
    chosen = []
    for work in pool:
        if recommender.normalize(work.title) in normalized:
            chosen.append(work)
    return chosen


# ---------------------------------------------------------------------------
# LLM interpretation (primary path)
# ---------------------------------------------------------------------------


def build_interpret_prompt(message: str, context: ConversationContext) -> List[dict]:
    pool = context.indexed()
    works_lines = []
    for index, work in enumerate(pool, 1):
        bits = [f"[{work.type}] {work.title}"]
        if work.creator:
            bits.append(work.creator)
        if work.year:
            bits.append(str(work.year))
        if work.matched_genres:
            bits.append(", ".join(work.matched_genres))
        works_lines.append(f"{index}. " + " — ".join(bits))

    history_lines = []
    for turn in context.history[-MAX_CONTEXT_TURNS:]:
        line = f"{turn['role']}: {str(turn['content'])[:400]}"
        if turn.get("works"):
            line += f" | obras: {', '.join(turn['works'])}"
        history_lines.append(line)

    system = (
        "Sos el intérprete del asistente de ReeStack. Tu única tarea es decidir "
        "qué quiere hacer el usuario, usando el historial y las obras ya mostradas. "
        "No inventes sinopsis, autores ni argumentos. Respondés solo JSON válido con "
        'la forma {"action":"recommend|details|compare|more|refine|chat|spoiler",'
        '"targets":[1,2],"spoilers":true|false,"query":"...","reply":"..."}. '
        "targets son índices 1-based de la lista OBRAS. Usá reply solo cuando "
        "action sea chat y la respuesta no dependa de datos que no tenés. "
        "Si el usuario pide el final o habla de spoilers, action debe ser spoiler. "
        "Si pide otros títulos parecidos a uno anterior, action debe ser more con "
        "ese target. Si pregunta de qué trata o pide detalles de una obra anterior, "
        "action debe ser details y NO debés recomendar obras nuevas."
    )
    works_text = "\n".join(works_lines) or "(sin obras todavía)"
    history_text = "\n".join(history_lines) or "(sin historial)"
    user = "\n".join(
        [
            f"Mensaje actual: {message}",
            f"Preferencia de spoilers (false = sin spoilers): {str(context.spoilers_allowed).lower()}",
            "OBRAS disponibles:",
            works_text,
            "Historial:",
            history_text,
        ]
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


async def call_llm_json(messages: Sequence[dict]) -> Tuple[Optional[dict], List[str]]:
    """Call the configured LLM and parse a JSON object.

    Errors are returned as warning codes so the caller can degrade instead of
    failing the request.
    """
    settings = recommender.llm_settings()
    if not settings["key"]:
        return None, ["llm_key_missing"]

    payload = {"model": settings["model"], "messages": list(messages), "temperature": 0.2}
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
        return None, ["llm_timeout"]
    except httpx.HTTPError:
        return None, ["llm_unavailable"]

    if response.status_code == 429:
        return None, ["llm_quota_exceeded"]
    if response.status_code in (401, 403):
        return None, ["llm_invalid_key"]
    if response.status_code >= 500:
        return None, ["llm_upstream_error"]
    if response.status_code != 200:
        return None, [f"llm_status_{response.status_code}"]

    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        return None, ["llm_invalid_response"]

    parsed = recommender._extract_json(content)
    if not isinstance(parsed, dict):
        return None, ["llm_invalid_response"]
    return parsed, []


def _validate_decision(data: Dict[str, Any], message: str, context: ConversationContext) -> Optional[Dict[str, Any]]:
    action = str(data.get("action") or "").strip().lower()
    if action not in ACTIONS:
        return None

    pool = context.indexed()
    targets: List[Work] = []
    for raw in data.get("targets") or []:
        if isinstance(raw, str):
            wanted = recommender.normalize(raw)
            match = next(
                (work for work in pool if recommender.normalize(work.title) == wanted),
                None,
            )
            if match:
                targets.append(match)
            continue
        try:
            index = int(raw)
        except (TypeError, ValueError):
            continue
        if 0 < index <= len(pool):
            targets.append(pool[index - 1])

    if action in ("details", "compare", "spoiler") and not targets:
        targets = resolve_targets(message, context)
    if action in ("more",) and not targets:
        targets = resolve_targets(message, context)

    spoilers = data.get("spoilers")
    if spoilers is None:
        spoilers = context.spoilers_allowed

    return {
        "action": action,
        "targets": targets,
        "spoilers": bool(spoilers),
        "reply": str(data.get("reply") or "").strip(),
        "query": str(data.get("query") or "").strip(),
    }


async def interpret_turn(
    message: str,
    context: ConversationContext,
    *,
    allow_llm: bool = True,
) -> Tuple[Dict[str, Any], List[str], bool]:
    """Return ``(decision, warnings, used_llm)``.

    The LLM interprets first. Any failure falls back to the contextual
    heuristic and reports the reason in ``warnings``.
    """
    fallback = heuristic_decision(message, context)

    if not allow_llm:
        return fallback, [], False

    settings = recommender.llm_settings()
    if not settings["key"]:
        return fallback, ["llm_key_missing"], False

    data, warnings = await call_llm_json(build_interpret_prompt(message, context))
    if data is not None:
        decision = _validate_decision(data, message, context)
        if decision is not None:
            return decision, warnings, True
        warnings = list(warnings) + ["llm_invalid_response"]

    return fallback, warnings, False


# ---------------------------------------------------------------------------
# Catalogue details (real data only)
# ---------------------------------------------------------------------------


def _cache_key(work: Work) -> str:
    return f"details:{work.type}:{recommender.normalize(work.title)}"


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return " ".join(text.split())


def _first_sentences(text: str, count: int = 2) -> str:
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return " ".join(part for part in parts[:count] if part).strip()


def _best_match(title: str, results: Sequence[dict]) -> Optional[dict]:
    for result in results:
        if recommender._titles_match(title, result.get("title", "")):
            return result
    return None


def _open_library_description(payload: Any) -> Optional[str]:
    """Normalise the shapes Open Library uses for ``description``/``first_sentence``.

    The search endpoint returns a list of values, the work endpoint a dict with
    ``type``/``value``, and some records a plain string.
    """
    if isinstance(payload, dict):
        value = payload.get("value")
        return str(value).strip() if value else None
    if isinstance(payload, str):
        return payload.strip() or None
    if isinstance(payload, (list, tuple)):
        parts = [_open_library_description(item) for item in payload]
        joined = " ".join(part for part in parts if part).strip()
        return joined or None
    return None


async def _book_details(work: Work) -> Work:
    query = f"{work.title} {work.creator or ''}".strip()
    params = {
        "q": query,
        "fields": "key,title,author_name,first_publish_year,number_of_pages_median,first_sentence,subject",
        "limit": 5,
    }
    async with httpx.AsyncClient(
        timeout=15.0,
        headers={"User-Agent": catalog.USER_AGENT, "Accept": "application/json"},
    ) as client:
        response = await client.get(OPEN_LIBRARY_SEARCH_URL, params=params)
        if response.status_code == 200:
            docs = response.json().get("docs") or []
            match = _best_match(work.title, docs)
            if match:
                work.year = match.get("first_publish_year") or work.year
                if not work.creator:
                    work.creator = ", ".join(match.get("author_name") or []) or None
                pages = match.get("number_of_pages_median")
                if pages:
                    work.pages = int(pages)
                if not work.description:
                    work.description = _open_library_description(match.get("first_sentence"))
                key = match.get("key")
                if not work.description and key:
                    detailed = await client.get(OPEN_LIBRARY_WORK_URL.format(key=key))
                    if detailed.status_code == 200:
                        work.description = _open_library_description(
                            detailed.json().get("description")
                        )

        api_key = (os.getenv("GOOGLE_BOOKS_API_KEY") or "").strip()
        if api_key and (not work.description or not work.pages):
            extra = await client.get(
                catalog.GOOGLE_BOOKS_URL,
                params={
                    "q": f'intitle:"{work.title}"',
                    "maxResults": 5,
                    "key": api_key,
                },
            )
            if extra.status_code == 200:
                volumes = extra.json().get("items") or []
                best = None
                for volume in volumes:
                    candidate = catalog._normalize_google_book(volume)
                    if candidate and recommender._titles_match(work.title, candidate["title"]):
                        best = candidate
                        info = (volume or {}).get("volumeInfo") or {}
                        break
                if best:
                    work.description = work.description or best.get("description")
                    work.creator = work.creator or best.get("creator")
                    work.year = work.year or best.get("year")
                    page_count = info.get("pageCount") if "info" in locals() else None
                    if page_count:
                        work.pages = work.pages or int(page_count)
    return work


async def _screen_details(work: Work) -> Work:
    query = f"{work.title} {work.creator or ''}".strip()
    results, _source, _errors = await catalog.search_catalog_results(work.type, query)
    match = _best_match(work.title, results)
    if match:
        work.description = work.description or match.get("description")
        work.creator = work.creator or match.get("creator")
        work.year = work.year or match.get("year")
        work.source = work.source or match.get("source")
        work.external_id = work.external_id or (
            str(match.get("external_id")) if match.get("external_id") is not None else None
        )

    if work.type == "series" and work.external_id and str(work.external_id).isdigit():
        try:
            async with httpx.AsyncClient(
                timeout=15.0,
                headers={"User-Agent": catalog.USER_AGENT, "Accept": "application/json"},
            ) as client:
                show = await client.get(TVMAZE_SHOW_URL.format(external_id=work.external_id))
                if show.status_code == 200:
                    payload = show.json()
                    summary = _strip_html(payload.get("summary") or "")
                    work.description = work.description or summary or None
                    if payload.get("averageRuntime"):
                        work.runtime = int(payload["averageRuntime"])
        except (httpx.HTTPError, ValueError):
            pass

    api_key = (os.getenv("TMDB_API_KEY") or "").strip()
    if api_key and work.external_id and str(work.external_id).isdigit():
        kind = "movie" if work.type == "movie" else "tv"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    TMDB_DETAIL_URL.format(kind=kind, external_id=work.external_id),
                    params={"api_key": api_key, "language": "es-AR"},
                )
                if response.status_code == 200:
                    payload = response.json()
                    work.description = work.description or payload.get("overview") or None
                    if kind == "movie" and payload.get("runtime"):
                        work.runtime = int(payload["runtime"])
                    if kind == "tv":
                        episodes = payload.get("episode_run_time") or []
                        if episodes:
                            work.runtime = int(episodes[0])
        except (httpx.HTTPError, ValueError):
            pass

    if not work.description:
        kind = "film" if work.type == "movie" else "television"
        fallback, _error = await recommender._wikipedia_media(kind, work.title)
        if fallback:
            work.description = fallback[0].get("description")
            work.creator = work.creator or fallback[0].get("creator")
            work.year = work.year or fallback[0].get("year")

    return work


async def fetch_details(work: Work) -> Work:
    """Enrich one work with real catalogue data. Never raises."""
    cached = catalog._cache_get(_cache_key(work))
    if cached is not None:
        merged = Work.from_dict(cached)
        merged.reason = work.reason or merged.reason
        merged.matched_genres = work.matched_genres or merged.matched_genres
        return merged

    enriched = Work.from_dict(work.to_dict())
    try:
        if enriched.type == "book":
            enriched = await _book_details(enriched)
        elif enriched.type in ("movie", "series"):
            enriched = await _screen_details(enriched)
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        # Keep whatever the conversation already knew; the answer will say the
        # catalogue data is missing instead of inventing it.
        pass

    catalog._cache_set(_cache_key(work), enriched.to_dict())
    return enriched


# ---------------------------------------------------------------------------
# Answers
# ---------------------------------------------------------------------------


def _work_line(work: Work) -> str:
    meta = " — ".join(filter(None, [work.creator, str(work.year) if work.year else None]))
    return f"{work.title} ({meta})" if meta else work.title


def _detail_sentence(work: Work, spoilers_allowed: bool) -> str:
    if not work.description:
        return (
            f"{_work_line(work)}: el catálogo no devuelve sinopsis para esta obra, "
            "así que no voy a inventarla."
        )
    description = work.description
    if not spoilers_allowed:
        description = _first_sentences(description, 2)
    return f"{_work_line(work)}: {description}"


async def answer_details(
    targets: Sequence[Work],
    *,
    spoilers_allowed: bool,
    spoiler_request: bool,
) -> Dict[str, Any]:
    enriched = [await fetch_details(work) for work in targets]
    # Without spoilers we only show the opening of the synopsis. With spoilers
    # allowed we can show the whole catalogue description, but still never the
    # ending: that data is not in the catalogue.
    reveal = spoiler_request and spoilers_allowed
    lines = [
        _detail_sentence(work, True if reveal else spoilers_allowed)
        for work in enriched
    ]
    has_description = any(work.description for work in enriched)

    if spoiler_request:
        if spoilers_allowed:
            prefix = (
                "⚠️ Aviso de spoilers: lo que sigue es la sinopsis del catálogo y "
                "puede adelantar parte de la trama. No tengo el final en los datos, "
                "así que no voy a inventarlo."
            )
        else:
            prefix = "Sin spoilers: te cuento solo de qué trata, sin revelar el final."
        message = prefix + "\n\n" + "\n\n".join(lines)
    else:
        message = "\n\n".join(lines)

    return {
        "message": message,
        "recommendations": [],
        "works": enriched,
        "spoiler_warning": spoiler_request,
        "spoilers_revealed": bool(spoiler_request and spoilers_allowed and has_description),
    }


async def answer_compare(targets: Sequence[Work]) -> Dict[str, Any]:
    enriched = [await fetch_details(work) for work in targets]
    rows = []
    comparable: List[Tuple[Work, str, int]] = []

    for work in enriched:
        bits = [_work_line(work)]
        if work.description:
            bits.append(_first_sentences(work.description, 1))
        length_value = None
        length_unit = None
        if work.type == "book" and work.pages:
            length_value, length_unit = work.pages, "páginas"
        elif work.type in ("movie", "series") and work.runtime:
            length_value, length_unit = work.runtime, "minutos"
        if length_value:
            bits.append(f"{length_value} {length_unit}")
            comparable.append((work, length_unit, length_value))
        rows.append("- " + " | ".join(bits))

    message = "Comparo las obras de la conversación:\n" + "\n".join(rows)

    units = {unit for _work, unit, _value in comparable}
    if not comparable:
        message += (
            "\n\nNo tengo datos de páginas ni de duración para estas obras, "
            "así que no puedo decir cuál es más corta sin inventarlo."
        )
    elif len(units) > 1:
        message += (
            "\n\nTienen métricas distintas (páginas y minutos), así que no son "
            "comparables de forma directa."
        )
    else:
        shortest, unit, value = min(comparable, key=lambda row: row[2])
        missing = len(enriched) - len(comparable)
        message += f"\n\nLa más corta es {shortest.title}: {value} {unit}."
        if missing:
            message += f" No tengo el dato de extensión de {missing} de las obras."

    return {
        "message": message,
        "recommendations": [],
        "works": enriched,
        "spoiler_warning": False,
        "spoilers_revealed": False,
    }


def _fallback_chat(context: ConversationContext) -> str:
    if context.works:
        titles = ", ".join(work.title for work in context.works[-3:])
        return (
            f"Puedo seguir con esta conversación sobre {titles}: contarte de qué "
            "trata alguna, compararlas o buscar opciones parecidas. ¿Qué preferís?"
        )
    return (
        "Puedo recomendarte libros, películas, series, música o papers. "
        "Contame qué buscás: un género, un ánimo o una obra parecida a otra."
    )


async def answer_chat(
    message: str,
    context: ConversationContext,
    targets: Sequence[Work],
    *,
    allow_llm: bool,
) -> Dict[str, Any]:
    enriched = [await fetch_details(work) for work in targets] if targets else []

    if allow_llm:
        settings = recommender.llm_settings()
        if settings["key"]:
            data_lines = []
            for work in enriched:
                data_lines.append(
                    f"- {_work_line(work)}: {work.description or 'sin sinopsis en el catálogo'}"
                )
            system = (
                "Sos ReeIA, el asistente de ReeStack. Conversás en español rioplatense, "
                "conciso y cálido. Usá solo los DATOS provistos para hablar de obras: "
                "no inventes sinopsis, autores, páginas ni argumentos. Si falta un dato, "
                "decí que no lo tenés. No recomiendes obras nuevas en este turno."
            )
            user = (
                f"Historial:\n"
                + "\n".join(
                    f"{turn['role']}: {str(turn['content'])[:400]}"
                    for turn in context.history[-MAX_CONTEXT_TURNS:]
                )
                + f"\n\nDATOS:\n" + ("\n".join(data_lines) or "(sin obras en foco)")
                + f"\n\nPregunta: {message}"
            )
            data, warnings = await call_llm_json(
                [{"role": "system", "content": system}, {"role": "user", "content": user}]
            )
            reply = str((data or {}).get("reply") or "").strip()
            if reply:
                return {
                    "message": reply,
                    "recommendations": [],
                    "works": enriched,
                    "engine": "llm",
                    "warnings": warnings,
                    "spoiler_warning": False,
                    "spoilers_revealed": False,
                }
            return {
                "message": _fallback_chat(context),
                "recommendations": [],
                "works": enriched,
                "engine": "heuristic",
                "warnings": warnings or ["llm_invalid_response"],
                "spoiler_warning": False,
                "spoilers_revealed": False,
            }

    return {
        "message": _fallback_chat(context),
        "recommendations": [],
        "works": enriched,
        "engine": "heuristic",
        "warnings": [],
        "spoiler_warning": False,
        "spoilers_revealed": False,
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


async def handle_turn(
    db: Any,
    user: Any,
    message: str,
    context: ConversationContext,
    *,
    conversation_exists: bool = False,
    forced_type: Optional[str] = None,
    limit: int = 4,
    exclude_consumed: bool = True,
) -> Dict[str, Any]:
    """Route one user message and return a response body.

    The returned dict keeps every field the previous contract had and adds
    ``action``, ``context``, ``spoiler_warning`` and ``spoilers_revealed``.
    """
    parsed_intent = recommender.parse_request(message, forced_type)
    allow_llm = conversation_exists or bool(context.works)

    decision, warnings, used_llm = await interpret_turn(
        message, context, allow_llm=allow_llm
    )
    action = decision["action"]
    spoilers_allowed = _spoiler_preference(
        message, bool(decision.get("spoilers", context.spoilers_allowed))
    )
    preference_only = _only_spoiler_preference(message)
    if preference_only is not None and context.works:
        # Changing the spoiler policy is a conversation turn, not a new search.
        action = "chat"
    pool = context.indexed()
    titles = decision.get("targets") or []
    targets = (
        _targets_by_title(titles, pool)
        if titles and isinstance(titles[0], str)
        else list(titles)
    )
    if action in ("details", "compare", "spoiler") and not targets:
        targets = context.last_focus[-1:] or pool[-1:]

    if action in ("details", "compare", "spoiler") and not targets:
        action = "chat"

    result: Dict[str, Any] = {
        "message": "",
        "recommendations": [],
        "engine": "heuristic",
        "degraded": False,
        "warnings": list(warnings),
        "conversation_id": None,
        "intent": {},
        "action": action,
        "context": {"works": [work.title for work in targets]},
        "spoiler_warning": False,
        "spoilers_revealed": False,
        "works_for_turn": [],
    }

    if action in ("recommend", "more", "refine"):
        effective_type = forced_type
        seed_payload = None
        if action == "more" and targets:
            seed_payload = targets[0].to_dict()
            effective_type = targets[0].type

        recommendation_result = await recommender.recommend(
            db,
            user,
            message,
            forced_type=effective_type,
            limit=limit,
            exclude_consumed=exclude_consumed,
            exclude_titles=context.all_titles(),
            history=context.history,
            seed=seed_payload,
        )
        result.update(
            {
                "message": recommendation_result["message"],
                "recommendations": recommendation_result["recommendations"],
                "engine": recommendation_result["engine"],
                "degraded": recommendation_result["degraded"],
                "warnings": result["warnings"] + recommendation_result["warnings"],
                "works_for_turn": recommendation_result["recommendations"],
            }
        )
        if action == "more" and not result["recommendations"]:
            result["message"] = (
                "No encontré opciones nuevas parecidas a "
                f"{targets[0].title}. Probá con otro género o pedime que amplíe la búsqueda."
            )

    elif action == "details":
        answer = await answer_details(
            targets,
            spoilers_allowed=spoilers_allowed,
            spoiler_request=False,
        )
        result.update(answer)
        result["works_for_turn"] = [work.to_dict() for work in answer["works"]]

    elif action == "spoiler":
        answer = await answer_details(
            targets,
            spoilers_allowed=spoilers_allowed,
            spoiler_request=True,
        )
        result.update(answer)
        result["works_for_turn"] = [work.to_dict() for work in answer["works"]]

    elif action == "compare":
        answer = await answer_compare(targets)
        result.update(answer)
        result["works_for_turn"] = [work.to_dict() for work in answer["works"]]

    else:  # chat
        if preference_only is not None:
            message_text = (
                "Listo, sigo sin spoilers: te cuento de qué trata sin revelar el final."
                if preference_only is False
                else "Listo, ahora puedo contar más detalles con spoilers, avisando antes."
            )
            answer = {
                "message": message_text,
                "recommendations": [],
                "works": [],
                "engine": "heuristic",
                "warnings": [],
                "spoiler_warning": False,
                "spoilers_revealed": False,
            }
        else:
            answer = await answer_chat(
                message,
                context,
                targets or context.last_focus[-1:],
                allow_llm=allow_llm,
            )
        result.update(answer)
        result["works_for_turn"] = [work.to_dict() for work in answer["works"]]
        if answer.get("engine") == "llm":
            used_llm = True
        result["warnings"] = result["warnings"] + answer.get("warnings", [])

    if used_llm and action in ("recommend", "more", "refine", "chat"):
        result["engine"] = "llm"

    deduped = []
    for warning in result["warnings"]:
        if warning and warning not in deduped:
            deduped.append(warning)
    result["warnings"] = deduped
    result["degraded"] = any(warning.startswith("llm_") for warning in deduped)

    intent = parsed_intent.to_dict()
    intent.update(
        {
            "action": action,
            "targets": [work.title for work in targets],
            "spoilers_allowed": spoilers_allowed,
        }
    )
    result["intent"] = intent
    result["context"] = {
        "works": [work.title for work in targets],
        "available": [work.title for work in (context.last_batch or context.works)],
    }
    return result
