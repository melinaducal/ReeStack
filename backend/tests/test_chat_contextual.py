"""Multi-turn conversation tests for ReeIA.

Everything runs against the in-memory database from ``conftest.py``. The
catalogue and the detail lookups are faked, so no test touches ``reestack.db``
or the network.
"""

import dataclasses
from types import SimpleNamespace

import pytest

from app.routers import catalog
from app.services import assistant, recommender


class _FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload


def _book(title, creator, year, description):
    return {
        "external_id": f"ol-{title}",
        "title": title,
        "creator": creator,
        "year": year,
        "cover_url": None,
        "description": description,
        "source": "open_library",
    }


BOOKS = [
    _book(
        "El nombre de la rosa",
        "Umberto Eco",
        1980,
        "Un monje investiga un misterio de muertes en una abadía medieval.",
    ),
    _book(
        "El sabueso de los Baskerville",
        "Arthur Conan Doyle",
        1902,
        "Sherlock Holmes investiga un misterio con un perro fantasmal.",
    ),
    _book(
        "Diez negritos",
        "Agatha Christie",
        1939,
        "Diez personas atrapadas en una isla intentan resolver un misterio.",
    ),
]


@pytest.fixture(autouse=True)
def _isolated_environment(monkeypatch):
    for name in ("LLM_API_KEY", "TMDB_API_KEY", "GOOGLE_BOOKS_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    catalog._cache.clear()
    yield
    catalog._cache.clear()


@pytest.fixture
def fake_catalog(monkeypatch):
    state = {"calls": [], "handler": None}

    def default_handler(media_type, query):
        if media_type != "book":
            return [], []
        normalized = recommender.normalize(query)
        if "umberto eco" in normalized or "el nombre de la rosa" in normalized:
            return (
                [
                    BOOKS[0],
                    _book(
                        "El péndulo de Foucault",
                        "Umberto Eco",
                        1988,
                        "Una novela de misterio, conspiración y esoterismo.",
                    ),
                    _book(
                        "Baudolino",
                        "Umberto Eco",
                        2000,
                        "Un viaje medieval con misterio y aventura.",
                    ),
                ],
                [],
            )
        if "misterio" in normalized or "mystery" in normalized:
            return list(BOOKS), []
        return [], []

    state["handler"] = default_handler

    async def fake_search(media_type, query):
        state["calls"].append((media_type, query))
        results, errors = state["handler"](media_type, query)
        return list(results), "fake", list(errors)

    monkeypatch.setattr(catalog, "search_catalog_results", fake_search)
    return state


DETAIL_DATA = {
    "el nombre de la rosa": {
        "description": (
            "El monje franciscano Guillermo de Baskerville investiga una serie "
            "de muertes en una abadía medieval."
        ),
        "pages": 512,
        "creator": "Umberto Eco",
        "year": 1980,
    },
    "el sabueso de los baskerville": {
        "description": (
            "Sherlock Holmes investiga la muerte de Charles Baskerville y la "
            "leyenda de un perro diabólico en Dartmoor."
        ),
        "pages": 256,
        "creator": "Arthur Conan Doyle",
        "year": 1902,
    },
    "diez negritos": {
        "description": (
            "Diez personas son invitadas a una isla y empiezan a morir una por "
            "una mientras intentan descubrir al asesino."
        ),
        "pages": 320,
        "creator": "Agatha Christie",
        "year": 1939,
    },
}


@pytest.fixture
def fake_details(monkeypatch):
    async def fake_fetch(work):
        data = DETAIL_DATA.get(recommender.normalize(work.title))
        if not data:
            return work
        return dataclasses.replace(work, **data)

    monkeypatch.setattr(assistant, "fetch_details", fake_fetch)
    return fake_fetch


def _conversation(client, headers):
    return client.post("/chat/conversations", json={}, headers=headers).json()["id"]


def _send(client, headers, conversation_id, message, **extra):
    response = client.post(
        "/chat/recommend",
        json={"message": message, "conversation_id": conversation_id, **extra},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


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


def _first_batch(client, auth_headers, fake_catalog):
    conversation_id = _conversation(client, auth_headers)
    body = _send(
        client,
        auth_headers,
        conversation_id,
        "Recomendame tres libros de misterio",
        limit=3,
    )
    return conversation_id, body


# ---------------------------------------------------------------------------
# A-G mandatory cases
# ---------------------------------------------------------------------------


def test_a_recommends_three_mystery_books(client, auth_headers, fake_catalog):
    _conversation_id, body = _first_batch(client, auth_headers, fake_catalog)

    assert body["action"] == "recommend"
    assert len(body["recommendations"]) == 3
    assert all(item["reason"] for item in body["recommendations"])


def test_b_explains_second_without_recommending_again(
    client, auth_headers, fake_catalog, fake_details
):
    conversation_id, first = _first_batch(client, auth_headers, fake_catalog)
    calls_before = len(fake_catalog["calls"])

    body = _send(client, auth_headers, conversation_id, "¿De qué trata el segundo?")

    assert body["action"] == "details"
    assert body["recommendations"] == []
    assert "El sabueso de los Baskerville" in body["message"]
    assert "Sherlock Holmes" in body["message"]
    assert body["intent"]["targets"] == ["El sabueso de los Baskerville"]
    # Answering a question must not trigger a new recommendation search.
    assert len(fake_catalog["calls"]) == calls_before
    assert first["recommendations"][1]["title"] == "El sabueso de los Baskerville"


def test_c_compares_the_three_and_finds_the_shortest(
    client, auth_headers, fake_catalog, fake_details
):
    conversation_id, _first = _first_batch(client, auth_headers, fake_catalog)

    body = _send(client, auth_headers, conversation_id, "¿Cuál de los tres es más corto?")

    assert body["action"] == "compare"
    assert body["recommendations"] == []
    assert "La más corta" in body["message"]
    assert "El sabueso de los Baskerville" in body["message"]
    assert "256" in body["message"]


def test_c_does_not_invent_length_when_catalogue_has_no_data(
    client, auth_headers, fake_catalog, monkeypatch
):
    async def partial_details(work):
        data = DETAIL_DATA.get(recommender.normalize(work.title), {}).copy()
        data.pop("pages", None)
        if not data:
            return work
        return dataclasses.replace(work, **data)

    monkeypatch.setattr(assistant, "fetch_details", partial_details)
    conversation_id, _first = _first_batch(client, auth_headers, fake_catalog)

    body = _send(client, auth_headers, conversation_id, "¿Cuál de los tres es más corto?")

    assert body["action"] == "compare"
    assert "No tengo datos de páginas" in body["message"]


def test_d_more_like_the_first_uses_the_seed_work(
    client, auth_headers, fake_catalog, fake_details
):
    conversation_id, first = _first_batch(client, auth_headers, fake_catalog)
    first_titles = {item["title"] for item in first["recommendations"]}

    body = _send(client, auth_headers, conversation_id, "Dame otros parecidos al primero")

    assert body["action"] == "more"
    titles = [item["title"] for item in body["recommendations"]]
    assert titles
    assert set(titles).isdisjoint(first_titles)
    queries = " ".join(query for _type, query in fake_catalog["calls"]).lower()
    assert "umberto eco" in queries


def test_e_warns_about_spoilers_before_details(
    client, auth_headers, fake_catalog, fake_details
):
    conversation_id, _first = _first_batch(client, auth_headers, fake_catalog)

    body = _send(client, auth_headers, conversation_id, "Explicame el final")

    assert body["action"] == "spoiler"
    assert body["spoiler_warning"] is True
    assert body["spoilers_revealed"] is True
    assert "aviso de spoilers" in body["message"].lower()
    assert "no tengo el final" in body["message"].lower()


def test_e_respects_sin_spoilers(
    client, auth_headers, fake_catalog, fake_details
):
    conversation_id, _first = _first_batch(client, auth_headers, fake_catalog)

    body = _send(
        client,
        auth_headers,
        conversation_id,
        "Contame el final, sin spoilers",
    )

    assert body["intent"]["spoilers_allowed"] is False
    assert body["message"].startswith("Sin spoilers")
    assert body["spoilers_revealed"] is False


def test_e_preference_only_acknowledges_without_searching(
    client, auth_headers, fake_catalog, fake_details
):
    conversation_id, _first = _first_batch(client, auth_headers, fake_catalog)
    calls_before = len(fake_catalog["calls"])

    body = _send(client, auth_headers, conversation_id, "Sin spoilers")

    assert body["action"] == "chat"
    assert body["message"].startswith("Listo, sigo sin spoilers")
    assert body["intent"]["spoilers_allowed"] is False
    assert len(fake_catalog["calls"]) == calls_before


def test_f_context_survives_closing_and_reopening(
    client, auth_headers, fake_catalog, fake_details
):
    conversation_id, _first = _first_batch(client, auth_headers, fake_catalog)
    _send(client, auth_headers, conversation_id, "¿De qué trata el segundo?")

    turns = client.get(
        f"/chat/conversations/{conversation_id}", headers=auth_headers
    ).json()
    assert [turn["role"] for turn in turns] == [
        "user",
        "assistant",
        "user",
        "assistant",
    ]
    assert turns[1]["recommendations"][0]["title"] == "El nombre de la rosa"

    # Reopening is simulated by a fresh request: the backend rebuilds the
    # context from the persisted turns every time.
    body = _send(client, auth_headers, conversation_id, "¿Y el tercero?")

    assert body["action"] == "details"
    assert body["intent"]["targets"] == ["Diez negritos"]
    assert "Agatha Christie" in body["message"]


def test_g_users_never_share_conversation_context(
    client, fake_catalog, fake_details
):
    owner = _register(client, "context-owner@example.com")
    other = _register(client, "context-other@example.com")
    conversation_id, _first = _first_batch(client, owner, fake_catalog)

    assert (
        client.get(
            f"/chat/conversations/{conversation_id}", headers=other
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/chat/recommend",
            json={"message": "¿De qué trata el segundo?", "conversation_id": conversation_id},
            headers=other,
        ).status_code
        == 404
    )

    own_conversation = _conversation(client, other)
    body = _send(client, other, own_conversation, "¿De qué trata el segundo?")

    assert body["action"] == "chat"
    assert body["recommendations"] == []
    assert "El nombre de la rosa" not in body["message"]


# ---------------------------------------------------------------------------
# LLM-driven interpretation
# ---------------------------------------------------------------------------


def test_interpret_prompt_includes_history_and_previous_works():
    turns = [
        SimpleNamespace(role="user", content="Recomendame tres libros de misterio", recommendations=None),
        SimpleNamespace(
            role="assistant",
            content="Encontré 3 opciones.",
            recommendations='{"kind": "recommend", "works": [{"title": "El nombre de la rosa", "type": "book", "creator": "Umberto Eco"}]}',
        ),
        SimpleNamespace(role="user", content="¿De qué trata el segundo?", recommendations=None),
    ]
    context = assistant.build_context(turns)

    prompt = assistant.build_interpret_prompt("¿De qué trata el segundo?", context)
    user_message = prompt[1]["content"]

    assert "El nombre de la rosa" in user_message
    assert "Recomendame tres libros de misterio" in user_message
    assert "Umberto Eco" in user_message


def test_llm_interpretation_resolves_the_second_work(
    client, auth_headers, fake_catalog, fake_details, monkeypatch
):
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    captured = {}

    async def fake_llm(messages):
        user_text = messages[-1]["content"]
        captured["prompt"] = user_text
        if "segundo" in user_text:
            return {"action": "details", "targets": [2], "reply": ""}, []
        return {"action": "recommend", "targets": []}, []

    async def no_proposals(*args, **kwargs):
        return [], []

    monkeypatch.setattr(assistant, "call_llm_json", fake_llm)
    monkeypatch.setattr(recommender, "propose_titles", no_proposals)

    conversation_id = _conversation(client, auth_headers)
    first = _send(
        client,
        auth_headers,
        conversation_id,
        "Recomendame tres libros de misterio",
        limit=3,
    )
    assert first["action"] == "recommend"

    body = _send(client, auth_headers, conversation_id, "¿De qué trata el segundo?")

    assert body["action"] == "details"
    assert body["recommendations"] == []
    assert "El sabueso de los Baskerville" in body["message"]
    assert "El nombre de la rosa" in captured["prompt"]


def test_llm_chat_answer_without_new_recommendations(
    client, auth_headers, fake_catalog, fake_details, monkeypatch
):
    monkeypatch.setenv("LLM_API_KEY", "test-key")

    async def fake_llm(messages):
        system = messages[0]["content"]
        if "intérprete" in system:
            user_text = messages[-1]["content"]
            current = next(
                line
                for line in user_text.splitlines()
                if line.startswith("Mensaje actual:")
            )
            if "Recomendame" in current:
                return {"action": "recommend", "targets": []}, []
            return {"action": "chat", "targets": [1]}, []
        return {
            "reply": "Según el catálogo, la primera es una novela de misterio medieval."
        }, []

    async def no_proposals(*args, **kwargs):
        return [], []

    monkeypatch.setattr(assistant, "call_llm_json", fake_llm)
    monkeypatch.setattr(recommender, "propose_titles", no_proposals)

    conversation_id = _conversation(client, auth_headers)
    _send(client, auth_headers, conversation_id, "Recomendame tres libros de misterio", limit=3)

    body = _send(client, auth_headers, conversation_id, "¿Es una novela triste?")

    assert body["action"] == "chat"
    assert body["recommendations"] == []
    assert body["message"] == (
        "Según el catálogo, la primera es una novela de misterio medieval."
    )
    assert body["engine"] == "llm"


def test_llm_failure_degrades_and_still_answers_with_context(
    client, auth_headers, fake_catalog, fake_details, monkeypatch
):
    monkeypatch.setenv("LLM_API_KEY", "test-key")

    async def failing_llm(messages):
        return None, ["llm_unavailable"]

    async def no_proposals(*args, **kwargs):
        return [], []

    monkeypatch.setattr(assistant, "call_llm_json", failing_llm)
    monkeypatch.setattr(recommender, "propose_titles", no_proposals)

    conversation_id = _conversation(client, auth_headers)
    _send(client, auth_headers, conversation_id, "Recomendame tres libros de misterio", limit=3)

    body = _send(client, auth_headers, conversation_id, "¿De qué trata el segundo?")

    assert body["action"] == "details"
    assert "El sabueso de los Baskerville" in body["message"]
    assert "llm_unavailable" in body["warnings"]
    assert body["degraded"] is True


def test_detail_lookup_prefers_the_work_over_derivative_books():
    results = [
        {
            "title": 'Para leer "El nombre de la rosa" de Umberto Eco',
            "number_of_pages_median": 196,
        },
        {"title": "El Nombre de la Rosa", "number_of_pages_median": None},
        {"title": "Il nome della rosa", "number_of_pages_median": 533},
    ]

    match = assistant._best_match("El nombre de la rosa", results)

    assert match is results[1]


def test_open_library_description_accepts_list_and_dict_shapes():
    assert assistant._open_library_description(["First line."]) == "First line."
    assert (
        assistant._open_library_description({"type": "/type/text", "value": "Text."})
        == "Text."
    )
    assert assistant._open_library_description([]) is None


def test_recommendation_prompt_lists_already_shown_works():
    intent = recommender.parse_request("más libros de misterio")
    profile = recommender.TasteProfile()
    history = [
        {
            "role": "assistant",
            "content": "Encontré opciones.",
            "works": ["El nombre de la rosa", "Diez negritos"],
        }
    ]

    prompt = recommender.build_llm_prompt(intent, profile, history, 3, ["book"])

    assert "obras ya mostradas: El nombre de la rosa, Diez negritos" in prompt[1]["content"]
