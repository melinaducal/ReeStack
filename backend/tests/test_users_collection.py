"""Privacy, auth and persistence tests for public user collections."""

from app.models import Item


def _register_and_login(client, username, email):
    client.post(
        "/auth/register",
        json={
            "username": username,
            "first_name": "Test",
            "last_name": "User",
            "email": email,
            "birth_date": "1990-01-01",
            "password": "Password123!",
        },
    )
    response = client.post(
        "/auth/login",
        json={"email": email, "password": "Password123!"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_item(client, headers, **overrides):
    payload = {"title": "Item", "type": "book", "creator": "Autor"}
    payload.update(overrides)
    response = client.post("/items/", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def _current_user_id(client, headers):
    response = client.get("/users/me", headers=headers)
    assert response.status_code == 200
    return response.json()["id"]


def test_collection_requires_authentication(client, auth_headers):
    owner_id = _current_user_id(client, auth_headers)

    response = client.get(f"/users/{owner_id}/collection")

    assert response.status_code == 401


def test_collection_returns_only_public_items(client, auth_headers):
    owner_id = _current_user_id(client, auth_headers)
    public_item = _create_item(
        client,
        auth_headers,
        title="Publico",
        type="book",
        creator="Autora",
        cover_url="https://example.com/cover.jpg",
        rating=5,
        thoughts="Una resena publica",
        is_public=True,
    )
    _create_item(client, auth_headers, title="Privado", type="book", is_public=False)

    reader = _register_and_login(client, "reader1", "reader1@test.com")
    response = client.get(f"/users/{owner_id}/collection", headers=reader)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["title"] for item in body["items"]] == ["Publico"]

    item = body["items"][0]
    assert item["id"] == public_item["id"]
    assert item["type"] == "book"
    assert item["cover_url"] == "https://example.com/cover.jpg"
    assert item["creator"] == "Autora"
    assert item["rating"] == 5
    assert item["thoughts"] == "Una resena publica"


def test_collection_paginates_and_filters_by_type(client, auth_headers):
    owner_id = _current_user_id(client, auth_headers)
    for index in range(3):
        _create_item(client, auth_headers, title=f"Libro {index}", type="book")
    _create_item(client, auth_headers, title="Pelicula", type="movie")

    reader = _register_and_login(client, "reader2", "reader2@test.com")

    first_page = client.get(
        f"/users/{owner_id}/collection?page=1&limit=2", headers=reader
    ).json()
    second_page = client.get(
        f"/users/{owner_id}/collection?page=2&limit=2", headers=reader
    ).json()

    assert first_page["total"] == 4
    assert first_page["pages"] == 2
    assert first_page["limit"] == 2
    assert len(first_page["items"]) == 2
    assert len(second_page["items"]) == 2
    assert {i["id"] for i in first_page["items"]}.isdisjoint(
        {i["id"] for i in second_page["items"]}
    )

    only_books = client.get(
        f"/users/{owner_id}/collection?type=book", headers=reader
    ).json()
    assert only_books["total"] == 3
    assert all(item["type"] == "book" for item in only_books["items"])

    only_movies = client.get(
        f"/users/{owner_id}/collection?type=movie", headers=reader
    ).json()
    assert only_movies["total"] == 1
    assert only_movies["items"][0]["title"] == "Pelicula"


def test_collection_of_unknown_user_returns_404(client, auth_headers):
    response = client.get("/users/999999/collection", headers=auth_headers)

    assert response.status_code == 404


def test_owner_can_toggle_visibility_and_change_persists(
    client, auth_headers, db_session
):
    owner_id = _current_user_id(client, auth_headers)
    item = _create_item(client, auth_headers, title="Cambiante", is_public=True)

    response = client.patch(
        f"/items/{item['id']}/visibility",
        headers=auth_headers,
        json={"is_public": False},
    )
    assert response.status_code == 200
    assert response.json()["is_public"] is False

    stored = db_session.query(Item).filter(Item.id == item["id"]).first()
    db_session.refresh(stored)
    assert stored.is_public is False

    reader = _register_and_login(client, "reader3", "reader3@test.com")
    collection = client.get(
        f"/users/{owner_id}/collection", headers=reader
    ).json()
    assert collection["total"] == 0

    # The owner still sees it in their own library.
    mine = client.get("/items/?mine=true", headers=auth_headers).json()
    assert [i["id"] for i in mine] == [item["id"]]
    assert client.get(f"/items/{item['id']}", headers=auth_headers).status_code == 200

    # Toggling back makes it public again.
    response = client.patch(
        f"/items/{item['id']}/visibility",
        headers=auth_headers,
        json={"is_public": True},
    )
    assert response.status_code == 200
    assert response.json()["is_public"] is True
    assert client.get(f"/users/{owner_id}/collection", headers=reader).json()[
        "total"
    ] == 1


def test_non_owner_cannot_change_visibility(client, auth_headers, db_session):
    item = _create_item(client, auth_headers, title="Ajeno", is_public=True)
    reader = _register_and_login(client, "reader4", "reader4@test.com")

    response = client.patch(
        f"/items/{item['id']}/visibility",
        headers=reader,
        json={"is_public": False},
    )

    assert response.status_code == 403
    stored = db_session.query(Item).filter(Item.id == item["id"]).first()
    db_session.refresh(stored)
    assert stored.is_public is True


def test_visibility_requires_authentication(client, auth_headers):
    item = _create_item(client, auth_headers, title="Sin token")

    response = client.patch(
        f"/items/{item['id']}/visibility", json={"is_public": False}
    )

    assert response.status_code == 401


def test_visibility_for_unknown_item_returns_404(client, auth_headers):
    response = client.patch(
        "/items/999999/visibility", headers=auth_headers, json={"is_public": False}
    )

    assert response.status_code == 404


def test_private_item_is_hidden_from_other_and_anonymous_users(client, auth_headers):
    item = _create_item(client, auth_headers, title="Secreto", is_public=False)
    reader = _register_and_login(client, "reader5", "reader5@test.com")

    other_response = client.get(f"/items/{item['id']}", headers=reader)
    anonymous_response = client.get(f"/items/{item['id']}")

    assert other_response.status_code == 404
    assert anonymous_response.status_code == 404
    assert client.get(f"/items/{item['id']}", headers=auth_headers).status_code == 200


def test_feed_hides_private_items_from_others(client, auth_headers):
    owner_id = _current_user_id(client, auth_headers)
    public_item = _create_item(client, auth_headers, title="Visible", is_public=True)
    _create_item(client, auth_headers, title="Oculto", is_public=False)

    reader = _register_and_login(client, "reader6", "reader6@test.com")
    feed = client.get("/items/feed", headers=reader).json()

    assert [i["title"] for i in feed] == ["Visible"]
    assert feed[0]["user_id"] == owner_id
    assert feed[0]["id"] == public_item["id"]

    # Owner still sees their own private item in the feed.
    owner_feed = client.get("/items/feed", headers=auth_headers).json()
    assert {i["title"] for i in owner_feed} == {"Visible", "Oculto"}


def test_public_profile_stats_only_count_public_items(client, auth_headers):
    owner_id = _current_user_id(client, auth_headers)
    _create_item(client, auth_headers, title="Publico", type="book", is_public=True)
    _create_item(client, auth_headers, title="Privado", type="movie", is_public=False)

    response = client.get(f"/users/{owner_id}/public")

    assert response.status_code == 200
    stats = response.json()["stats"]
    assert stats["items_count"] == 1
    assert stats["books"] == 1
    assert stats["movies"] == 0


def test_items_are_public_by_default_and_legacy_rows_stay_public(
    client, auth_headers, db_session
):
    created = _create_item(client, auth_headers, title="Por defecto")
    assert created["is_public"] is True

    legacy = Item(user_id=1, title="Sin campo explicito", type="book")
    db_session.add(legacy)
    db_session.commit()
    db_session.refresh(legacy)

    assert legacy.is_public is True


def test_put_update_accepts_visibility(client, auth_headers):
    item = _create_item(client, auth_headers, title="Editable")

    response = client.put(
        f"/items/{item['id']}", headers=auth_headers, json={"is_public": False}
    )

    assert response.status_code == 200
    assert response.json()["is_public"] is False
