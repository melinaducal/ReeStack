"""Isolated tests for the recommendation assistant.

Every test runs against the in-memory database from ``conftest.py`` and fakes
the catalogue and the LLM, so nothing touches ``reestack.db`` or the network.
"""

import pytest

from app.routers import catalog
from app.services import recommender


class _FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


class _FakeAsyncClient:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def post(self, *args, **kwargs):
        return self._response


def _book(title="El amor en los tiempos del cólera", creator="Gabriel García Márquez"):
    return {
        "external_id": f"ol-{title}",
        "title": title,
        "creator": creator,
        "year": 1985,
        "cover_url": "https://covers.openlibrary.org/b/id/1-M.jpg",
        "description": "Una historia de romance, misterio y amor.",
        "source": "open_library",
    }


@pytest.fixture(autouse=True)
def _isolated_environment(monkeypatch):
    """No keys, no cache and no Wikipedia fallback network calls."""
    for name in ("LLM_API_KEY", "TMDB_API_KEY", "GOOGLE_BOOKS_API_KEY"):
        monkeypatch.delenv(name, raising=False)

    async def _no_wikipedia(kind, query):
        return [], None

    monkeypatch.setattr(recommender, "_wikipedia_media", _no_wikipedia)
    catalog._cache.clear()
    yield
    catalog._cache.clear()


@pytest.fixture
def fake_catalog(monkeypatch):
    """Replace the catalogue with a controllable in-memory provider."""
    state = {"calls": [], "handler": lambda media_type, query: ([], [])}

    async def fake_search(media_type, query):
        state["calls"].append((media_type, query))
        results, errors = state["handler"](media_type, query)
        return list(results), "fake", list(errors)

    monkeypatch.setattr(catalog, "search_catalog_results", fake_search)
    return state


def _register(client, email):
    client.post(
        "/auth/register",
        json={
            "username": email.split("@")[0],
            "first_name": "Test",
            "last_name": "User",
            "email": email,
            "birth_date": "1990-01-01",
            "password": "Password123!",
        },
    )
    token = client.post(
        "/auth/login",
        json={"email": email, "password": "Password123!"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Request interpretation
# ---------------------------------------------------------------------------


def test_parse_request_detects_genres_and_happy_ending():
    intent = recommender.parse_request("Quiero un romance con misterio y final feliz")

    assert "romance" in intent.genres
    assert "mystery" in intent.genres
    assert intent.constraints["happy_ending"] is True
    assert intent.types == []


def test_parse_request_detects_media_type_and_reference_work():
    intent = recommender.parse_request("Recomendame una película parecida a Interestelar")

    assert intent.types == ["movie"]
    assert intent.similar_to is not None
    assert "interestelar" in intent.similar_to


def test_parse_request_is_accent_insensitive():
    assert "scifi" in recommender.parse_request("algo de ciencia ficción").genres
    assert "fantasy" in recommender.parse_request("Algo de fantasía").genres


# ---------------------------------------------------------------------------
# Authentication and degradation
# ---------------------------------------------------------------------------


def test_recommend_requires_authentication(client, fake_catalog):
    response = client.post("/chat/recommend", json={"message": "Quiero un romance"})

    assert response.status_code == 401


def test_recommend_without_llm_key_still_answers(client, auth_headers, fake_catalog):
    fake_catalog["handler"] = lambda media_type, query: (
        ([_book()] if media_type == "book" else []),
        [],
    )

    response = client.post(
        "/chat/recommend",
        json={"message": "Quiero un romance con misterio y final feliz"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["engine"] == "heuristic"
    assert body["degraded"] is True
    assert "llm_key_missing" in body["warnings"]
    assert len(body["recommendations"]) == 1
    assert body["intent"]["genres"] == ["romance", "mystery"]


def test_recommend_returns_200_when_catalog_is_empty(client, auth_headers, fake_catalog):
    response = client.post(
        "/chat/recommend",
        json={"message": "Quiero un romance con misterio"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recommendations"] == []
    assert body["message"]


def test_recommend_survives_catalog_provider_errors(client, auth_headers, fake_catalog):
    fake_catalog["handler"] = lambda media_type, query: ([], ["open_library_request_failed"])

    response = client.post(
        "/chat/recommend",
        json={"message": "Quiero un romance"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert "open_library_request_failed" in response.json()["warnings"]


def test_movie_genre_uses_keyless_wikipedia_fallback(
    client, auth_headers, fake_catalog, monkeypatch
):
    calls = []

    async def fake_wikipedia(kind, query):
        calls.append((kind, query))
        return (
            [
                {
                    "external_id": "Contact (1997 American film)",
                    "title": "Contact (1997 American film)",
                    "creator": "Robert Zemeckis",
                    "year": 1997,
                    "cover_url": None,
                    "description": "1997 American science fiction drama film",
                    "source": "wikipedia",
                }
            ],
            None,
        )

    monkeypatch.setattr(recommender, "_wikipedia_media", fake_wikipedia)

    response = client.post(
        "/chat/recommend",
        json={"message": "Quiero una película de ciencia ficción"},
        headers=auth_headers,
    )

    body = response.json()
    assert calls == [("film", "science fiction")]
    assert body["recommendations"][0]["title"] == "Contact (1997 American film)"
    assert body["recommendations"][0]["source"] == "wikipedia"


# ---------------------------------------------------------------------------
# Verified works and explanations
# ---------------------------------------------------------------------------


def test_every_recommendation_explains_the_match(client, auth_headers, fake_catalog):
    fake_catalog["handler"] = lambda media_type, query: (
        ([_book()] if media_type == "book" else []),
        [],
    )

    response = client.post(
        "/chat/recommend",
        json={"message": "Quiero un romance con misterio"},
        headers=auth_headers,
    )

    recommendation = response.json()["recommendations"][0]
    assert recommendation["reason"]
    assert recommendation["matched_genres"] == ["romance", "misterio"]
    assert recommendation["source"] == "open_library"


def test_llm_proposals_must_exist_in_the_catalog(client, auth_headers, fake_catalog, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")

    async def fake_proposals(intent, profile, history, limit, types):
        return (
            [
                {"title": "El amor en los tiempos del cólera", "type": "book", "creator": "Gabriel García Márquez", "reason": "Romance y misterio clásico."},
                {"title": "La novela inventada por el modelo", "type": "book", "creator": "Nadie", "reason": "No existe."},
            ],
            [],
        )

    monkeypatch.setattr(recommender, "propose_titles", fake_proposals)
    fake_catalog["handler"] = lambda media_type, query: (
        ([_book()] if media_type == "book" else []),
        [],
    )

    response = client.post(
        "/chat/recommend",
        json={"message": "Quiero un romance con misterio"},
        headers=auth_headers,
    )

    body = response.json()
    titles = [item["title"] for item in body["recommendations"]]
    assert body["engine"] == "llm"
    assert "El amor en los tiempos del cólera" in titles
    assert "La novela inventada por el modelo" not in titles
    assert "llm_suggestions_not_in_catalog" in body["warnings"]


def test_llm_quota_errors_fall_back_to_heuristics(client, auth_headers, fake_catalog, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setattr(
        recommender.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeAsyncClient(_FakeResponse(429)),
    )
    fake_catalog["handler"] = lambda media_type, query: (
        ([_book()] if media_type == "book" else []),
        [],
    )

    response = client.post(
        "/chat/recommend",
        json={"message": "Quiero un romance"},
        headers=auth_headers,
    )

    body = response.json()
    assert response.status_code == 200
    assert "llm_quota_exceeded" in body["warnings"]
    assert body["engine"] == "heuristic"
    assert body["recommendations"]


# ---------------------------------------------------------------------------
# Library awareness
# ---------------------------------------------------------------------------


def test_recommend_excludes_titles_already_in_the_library(
    client, auth_headers, fake_catalog
):
    client.post(
        "/items",
        json={"title": "El amor en los tiempos del cólera", "type": "book", "rating": 5},
        headers=auth_headers,
    )
    fake_catalog["handler"] = lambda media_type, query: (
        (
            [_book(), _book(title="Cien años de soledad", creator="Gabriel García Márquez")]
            if media_type == "book"
            else []
        ),
        [],
    )

    response = client.post(
        "/chat/recommend",
        json={"message": "Quiero un romance con misterio"},
        headers=auth_headers,
    )

    titles = [item["title"] for item in response.json()["recommendations"]]
    assert "El amor en los tiempos del cólera" not in titles
    assert "Cien años de soledad" in titles


def test_recommend_uses_ratings_to_explain_creator_affinity(
    client, auth_headers, fake_catalog
):
    client.post(
        "/items",
        json={"title": "Cien años de soledad", "type": "book", "rating": 5,
              "creator": "Gabriel García Márquez"},
        headers=auth_headers,
    )
    fake_catalog["handler"] = lambda media_type, query: (
        ([_book(title="El otoño del patriarca")] if media_type == "book" else []),
        [],
    )

    response = client.post(
        "/chat/recommend",
        json={"message": "Quiero un romance"},
        headers=auth_headers,
    )

    recommendation = response.json()["recommendations"][0]
    assert "Gabriel García Márquez" in recommendation["reason"]


def test_library_of_another_user_is_not_used(client, fake_catalog):
    first = _register(client, "reader-one@example.com")
    second = _register(client, "reader-two@example.com")

    client.post(
        "/items",
        json={"title": "El amor en los tiempos del cólera", "type": "book", "rating": 5},
        headers=first,
    )
    fake_catalog["handler"] = lambda media_type, query: (
        ([_book()] if media_type == "book" else []),
        [],
    )

    response = client.post(
        "/chat/recommend",
        json={"message": "Quiero un romance"},
        headers=second,
    )

    titles = [item["title"] for item in response.json()["recommendations"]]
    assert titles == ["El amor en los tiempos del cólera"]


# ---------------------------------------------------------------------------
# Conversations per user
# ---------------------------------------------------------------------------


def test_conversation_keeps_turns_for_its_owner(client, auth_headers, fake_catalog):
    fake_catalog["handler"] = lambda media_type, query: (
        ([_book()] if media_type == "book" else []),
        [],
    )
    conversation_id = client.post(
        "/chat/conversations", json={}, headers=auth_headers
    ).json()["id"]

    response = client.post(
        "/chat/recommend",
        json={"message": "Quiero un romance", "conversation_id": conversation_id},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["conversation_id"] == conversation_id

    turns = client.get(
        f"/chat/conversations/{conversation_id}", headers=auth_headers
    ).json()
    assert [turn["role"] for turn in turns] == ["user", "assistant"]
    assert turns[1]["recommendations"][0]["title"] == "El amor en los tiempos del cólera"


def test_conversations_are_not_shared_between_users(client, fake_catalog):
    owner = _register(client, "owner@example.com")
    other = _register(client, "other@example.com")
    conversation_id = client.post(
        "/chat/conversations", json={"title": "Mi historial"}, headers=owner
    ).json()["id"]

    assert client.get("/chat/conversations", headers=other).json() == []
    assert (
        client.get(f"/chat/conversations/{conversation_id}", headers=other).status_code
        == 404
    )
    assert (
        client.post(
            "/chat/recommend",
            json={"message": "Quiero un romance", "conversation_id": conversation_id},
            headers=other,
        ).status_code
        == 404
    )


def test_unknown_conversation_returns_404(client, auth_headers):
    response = client.post(
        "/chat/recommend",
        json={"message": "Quiero un romance", "conversation_id": 9999},
        headers=auth_headers,
    )

    assert response.status_code == 404


def test_conversation_does_not_repeat_recommendations(client, auth_headers, fake_catalog):
    fake_catalog["handler"] = lambda media_type, query: (
        (
            [
                _book(),
                _book(title="Cien años de soledad"),
                _book(title="El otoño del patriarca"),
            ]
            if media_type == "book"
            else []
        ),
        [],
    )
    conversation_id = client.post(
        "/chat/conversations", json={}, headers=auth_headers
    ).json()["id"]

    first = client.post(
        "/chat/recommend",
        json={"message": "Quiero un romance", "conversation_id": conversation_id, "limit": 2},
        headers=auth_headers,
    ).json()
    second = client.post(
        "/chat/recommend",
        json={"message": "Dame otro romance", "conversation_id": conversation_id, "limit": 2},
        headers=auth_headers,
    ).json()

    first_titles = {item["title"] for item in first["recommendations"]}
    second_titles = {item["title"] for item in second["recommendations"]}
    assert first_titles & second_titles == set()


def test_delete_conversation_only_affects_the_owner(client, auth_headers):
    conversation_id = client.post(
        "/chat/conversations", json={}, headers=auth_headers
    ).json()["id"]

    assert (
        client.delete(f"/chat/conversations/{conversation_id}", headers=auth_headers).status_code
        == 204
    )
    assert client.get("/chat/conversations", headers=auth_headers).json() == []


# ---------------------------------------------------------------------------
# Existing endpoint regression
# ---------------------------------------------------------------------------


def test_save_recommendation_keeps_assigning_the_current_user(client, auth_headers):
    response = client.post(
        "/chat/save",
        json={
            "title": "Cien años de soledad",
            "type": "book",
            "creator": "Gabriel García Márquez",
            "reason": "Te gustó el realismo mágico",
            "year": 1967,
        },
        headers=auth_headers,
    )

    assert response.status_code == 200
    item_id = response.json()["id"]
    item = client.get(f"/items/{item_id}", headers=auth_headers).json()
    assert item["title"] == "Cien años de soledad"
    assert item["year"] == 1967
